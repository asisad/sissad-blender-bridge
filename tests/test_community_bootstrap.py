import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from sissad_blender_bridge import BridgeClient
from sissad_blender_bridge import community_bootstrap as bootstrap


@pytest.fixture
def missing_config(monkeypatch):
    for key in bootstrap.DISABLE_FLAGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delitem(sys.modules, "blender_mcp.config", raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)


def test_missing_config_requires_existing_explicit_opt_out(missing_config, monkeypatch):
    assert bootstrap.install_disabled_telemetry_config() is False
    assert "blender_mcp.config" not in sys.modules
    monkeypatch.setenv("BLENDER_MCP_DISABLE_TELEMETRY", "true")
    try:
        assert bootstrap.install_disabled_telemetry_config() is True
        config = sys.modules["blender_mcp.config"].telemetry_config
        assert vars(config) == {"enabled": False}
    finally:
        sys.modules.pop("blender_mcp.config", None)


def test_existing_config_and_privacy_flags_are_not_changed(missing_config, monkeypatch):
    existing = ModuleType("blender_mcp.config")
    existing.telemetry_config = SimpleNamespace(enabled=True)
    monkeypatch.setitem(sys.modules, "blender_mcp.config", existing)
    monkeypatch.setenv("DISABLE_TELEMETRY", "1")
    monkeypatch.setenv("BLENDER_MCP_SAFE_MODE", "1")
    before = dict(os.environ)
    assert bootstrap.install_disabled_telemetry_config() is False
    assert sys.modules["blender_mcp.config"] is existing
    assert existing.telemetry_config.enabled is True
    assert dict(os.environ) == before


def test_real_config_module_is_not_shadowed(missing_config, monkeypatch):
    monkeypatch.setenv("DISABLE_TELEMETRY", "true")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert bootstrap.install_disabled_telemetry_config() is False
    assert "blender_mcp.config" not in sys.modules


def test_community_launch_uses_own_adapter_preserves_args_environment(tmp_path):
    interpreter = tmp_path / ("python.exe" if os.name == "nt" else "python")
    interpreter.touch()
    command = tmp_path / ("mcp-for-blender.exe" if os.name == "nt" else "mcp-for-blender")
    config = tmp_path / "profiles.json"
    item = {"command": str(command), "args": ["--port", "9877"], "env": {
        "BLENDER_MCP_SAFE_MODE": "1", "DISABLE_TELEMETRY": "true", "BLENDER_HOST": "127.0.0.1"}}
    config.write_text(json.dumps({"profiles": {"community52": item}}))
    parameters = BridgeClient(config)._stdio_parameters(item)
    assert parameters.command == str(interpreter)
    assert parameters.args == [str(Path(bootstrap.__file__)), "--port", "9877"]
    assert {key: parameters.env[key] for key in item["env"]} == item["env"]
    assert item["command"] == str(command)


def test_pinned_upstream_status_reads_real_consent_with_missing_config():
    """Run the installed upstream status implementation, without Blender or network."""
    root = Path(__file__).resolve().parents[1]
    interpreter = root / ".runtime" / "venvs" / "community" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.is_file():
        pytest.skip("Optional pinned Community installation is not present")
    code = r'''
import asyncio, json, os, runpy, sys
from types import SimpleNamespace
bootstrap = runpy.run_path(sys.argv[1])
flags = {key: os.environ.pop(key, None) for key in bootstrap['DISABLE_FLAGS']}
assert bootstrap['install_disabled_telemetry_config']() is False
from blender_mcp import telemetry
try:
    telemetry.TelemetryCollector()
except ModuleNotFoundError as error:
    assert error.name == 'blender_mcp.config'
else:
    raise AssertionError('Missing telemetry config was silently fabricated without opt-out')
for key, value in flags.items():
    if value is not None:
        os.environ[key] = value
installed = bootstrap['install_disabled_telemetry_config']()
assert installed or __import__('importlib.util').util.find_spec('blender_mcp.config') is not None
from blender_mcp import server
from blender_mcp.safe_mode import safe_mode_enabled, validate_code, SandboxViolation
assert safe_mode_enabled()
try:
    validate_code('import os')
except SandboxViolation:
    pass
else:
    raise AssertionError('Safe mode import guard was bypassed')
telemetry.TelemetryCollector._get_or_create_uuid = lambda self: 'test-memory-only'
telemetry.threading.Thread.start = lambda self: None
calls = []
class Connection:
    def send_command(self, name, *args):
        calls.append(name)
        if name == 'get_telemetry_consent':
            return {'consent': False}
        return {'enabled': False}
server.get_blender_connection = lambda: Connection()
handshake = SimpleNamespace(up_to_date=True, protocol_version=1, addon_version='test',
    capabilities=[], blender_version='test', premium_generators=[], source='test', warning=None)
def handshake_read(connection):
    server._addon_handshake = handshake
server._maybe_handshake_addon = handshake_read
status = json.loads(asyncio.run(server.get_addon_status(None)))
assert status['telemetry_consent'] is False
assert 'get_telemetry_consent' in calls
collector = telemetry.get_telemetry()
assert collector.config.enabled is False
collector._send_event = lambda event: (_ for _ in ()).throw(AssertionError('telemetry sent'))
collector.record_event(telemetry.EventType.TOOL_EXECUTION, tool_name='test')
assert collector._queue.empty()
collector.invalidate_consent_cache()
server.get_blender_connection = lambda: (_ for _ in ()).throw(ConnectionError('unreachable'))
assert collector.check_user_consent() is None
print(json.dumps({'status_consent': status['telemetry_consent'], 'unreachable_consent': None,
    'telemetry_queued': collector._queue.qsize()}))
'''
    environment = dict(os.environ, DISABLE_TELEMETRY="true", BLENDER_MCP_DISABLE_TELEMETRY="true", BLENDER_MCP_SAFE_MODE="1")
    result = subprocess.run([str(interpreter), "-c", code, str(Path(bootstrap.__file__))],
        env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status_consent": False, "unreachable_consent": None, "telemetry_queued": 0}


def test_deployed_compatibility_file_fails_closed_without_opt_out(monkeypatch):
    import runpy

    for key in bootstrap.DISABLE_FLAGS:
        monkeypatch.delenv(key, raising=False)
    compatibility = Path(bootstrap.__file__).with_name("community_disabled_config.py")
    with pytest.raises(ModuleNotFoundError) as error:
        runpy.run_path(str(compatibility))
    assert error.value.name == "blender_mcp.config"
    monkeypatch.setenv("DISABLE_TELEMETRY", "true")
    result = runpy.run_path(str(compatibility))
    assert vars(result["telemetry_config"]) == {"enabled": False}


@pytest.mark.parametrize("existing", [False, True])
def test_cached_client_migration_never_replaces_configuration(tmp_path, monkeypatch, capsys, existing):
    import runpy

    script = Path(__file__).resolve().parents[1] / "scripts/repair-community-status.py"
    package = tmp_path / "blender_mcp"
    package.mkdir()
    (package / "telemetry.py").write_text("# test client marker")
    target = package / "config.py"
    original = b"# real upstream configuration must be preserved\n"
    if existing:
        target.write_bytes(original)
    config = tmp_path / "profiles.json"
    config.write_text(json.dumps({"profiles": {"community": {"command": str(tmp_path / "mcp-for-blender.exe"),
        "env": {"DISABLE_TELEMETRY": "true"}}}}))
    monkeypatch.setattr(sys, "argv", [str(script), "--config", str(config), "--profile", "community"])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps([str(package)])))
    namespace = runpy.run_path(str(script))
    namespace["main"]()
    first = json.loads(capsys.readouterr().out)
    assert first["changed"] is (not existing)
    expected = original if existing else Path(bootstrap.__file__).with_name("community_disabled_config.py").read_bytes()
    assert target.read_bytes() == expected
    namespace["main"]()
    assert json.loads(capsys.readouterr().out)["changed"] is False
    assert target.read_bytes() == expected


def test_cached_client_migration_requires_existing_opt_out(tmp_path, monkeypatch):
    import runpy
    from sissad_blender_bridge import BridgeError

    for key in bootstrap.DISABLE_FLAGS:
        monkeypatch.delenv(key, raising=False)
    script = Path(__file__).resolve().parents[1] / "scripts/repair-community-status.py"
    config = tmp_path / "profiles.json"
    config.write_text(json.dumps({"profiles": {"community": {"command": str(tmp_path / "mcp-for-blender.exe")}}}))
    monkeypatch.setattr(sys, "argv", [str(script), "--config", str(config), "--profile", "community"])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("No child should launch without opt-out"))
    namespace = runpy.run_path(str(script))
    with pytest.raises(BridgeError) as error:
        namespace["main"]()
    assert error.value.code == "privacy_required"
