import asyncio
import base64
from contextlib import asynccontextmanager
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, ImageContent, TextContent, Tool

import sissad_blender_bridge.client as module
from sissad_blender_bridge import BridgeClient, BridgeError
from sissad_blender_bridge.cli import main


@pytest.fixture
def client(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"profiles": {"lab": {"command": "python", "args": ["server.py"], "env": {"BLENDER_PORT": "9876"}}}}))
    return BridgeClient(config, lock_path=tmp_path / "lock")


@pytest.mark.parametrize("data", [{}, {"profiles": []}, {"profiles": {"lab": {"command": "python", "oops": 1}}}, {"profiles": {"lab": {"command": "python", "env": {"API_KEY": "private"}}}}, {"profiles": {"lab": {"command": "python", "args": "server.py"}}}])
def test_invalid_config(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    with pytest.raises(BridgeError, match="."):
        BridgeClient(path)


def test_lock_release_after_exception_and_contention(tmp_path):
    path = tmp_path / "writer.lock"
    with pytest.raises(RuntimeError):
        with module.writer_lock(path):
            with pytest.raises(BridgeError) as caught:
                with module.writer_lock(path):
                    pytest.fail("Concurrent lock allowed")
            assert caught.value.code == "busy"
            raise RuntimeError()
    with module.writer_lock(path):
        assert path.exists()


def test_lock_excludes_other_process(tmp_path):
    path = tmp_path / "writer.lock"
    child = "from pathlib import Path; from sissad_blender_bridge.client import writer_lock; import sys\nwith writer_lock(Path(sys.argv[1])): pass"
    with module.writer_lock(path):
        result = subprocess.run([sys.executable, "-c", child, str(path)], capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert "Another bridge call is in progress" in result.stderr
    result = subprocess.run([sys.executable, "-c", child, str(path)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0


def test_transport_initialize_pagination_call_and_environment(client, monkeypatch):
    events = []
    monkeypatch.setenv("BRIDGE_TEST_INHERITED", "present")

    @asynccontextmanager
    async def transport(parameters, errlog):
        assert parameters.env["BLENDER_PORT"] == "9876"
        assert parameters.env["BRIDGE_TEST_INHERITED"] == "present"
        assert parameters.cwd == str(client.config_path.parent)
        yield "read", "write"

    class Session:
        def __init__(self, read, write):
            assert (read, write) == ("read", "write")
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def initialize(self):
            events.append("initialize")
        async def list_tools(self, cursor=None):
            events.append(cursor)
            return SimpleNamespace(tools=[Tool(name="inspect" if cursor is None else "edit", inputSchema={"type": "object"})], nextCursor="next" if cursor is None else None)
        async def call_tool(self, name, arguments):
            events.append((name, arguments))
            return CallToolResult(content=[TextContent(type="text", text="done")])

    monkeypatch.setattr(module, "stdio_client", transport)
    monkeypatch.setattr(module, "ClientSession", Session)
    result = asyncio.run(client.list_tools("lab"))
    assert [t["name"] for t in result["tools"]] == ["inspect", "edit"]
    result = asyncio.run(client.call_tool("lab", "edit", {"x": 2}))
    assert result["content"][0]["text"] == "done"
    assert events == ["initialize", None, "next", "initialize", ("edit", {"x": 2})]


def test_bad_output_path_rejected_before_dispatch(client, tmp_path, monkeypatch):
    async def fail(*args, **kwargs):
        pytest.fail("Transport must not run")
    monkeypatch.setattr(client, "_request", fail)
    with pytest.raises(BridgeError) as caught:
        asyncio.run(client.call_tool("lab", "inspect", {}, output_dir=tmp_path / "missing"))
    assert caught.value.code == "output_invalid"


def test_image_saved_only_on_opt_in(tmp_path):
    result = CallToolResult(content=[ImageContent(type="image", mimeType="image/png", data=base64.b64encode(b"example-image").decode())])
    assert module.serialize_result(result)["content"][0] == {"type": "image", "mimeType": "image/png", "saved": False}
    saved = module.serialize_result(result, tmp_path)["content"][0]
    assert Path(saved["path"]).parent == tmp_path
    assert Path(saved["path"]).read_bytes() == b"example-image"


def test_transport_error_no_retry_no_secret(client, monkeypatch):
    calls = []
    @asynccontextmanager
    async def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("credential-should-never-be-printed")
        yield
    monkeypatch.setattr(module, "stdio_client", fail)
    with pytest.raises(BridgeError) as caught:
        asyncio.run(client.call_tool("lab", "edit", {}))
    assert calls == [1]
    assert "credential-should-never-be-printed" not in str(caught.value)
    with module.writer_lock(client.lock_path):
        pass


def test_timeout_is_uncertain_and_lock_released(client, monkeypatch):
    @asynccontextmanager
    async def stalled(*args, **kwargs):
        await asyncio.sleep(10)
        yield
    monkeypatch.setattr(module, "stdio_client", stalled)
    with pytest.raises(BridgeError) as caught:
        asyncio.run(client.call_tool("lab", "edit", {}, timeout=0.001))
    assert caught.value.code == "timeout"
    assert "may still be running" in str(caught.value)
    with module.writer_lock(client.lock_path):
        pass


def test_redact_known_secret(monkeypatch):
    monkeypatch.setenv("EXAMPLE_API_KEY", "known-private-value")
    assert module.redact({"password": "abc", "message": "contains known-private-value"}) == {"password": "[REDACTED]", "message": "contains [REDACTED]"}


def test_cli_profiles_and_invalid_arguments(client, capsys):
    assert main(["--config", str(client.config_path), "profiles"]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == {"profiles": ["lab"]}
    assert main(["--config", str(client.config_path), "call", "--profile", "lab", "--tool", "edit", "--arguments", "[]"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "arguments_invalid"
