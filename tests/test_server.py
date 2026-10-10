import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace

import pytest

from mcp import types

from sissad_blender_bridge import BridgeClient
from sissad_blender_bridge.server import make_server
import sissad_blender_bridge.client as client_module


def test_proxy_preserves_images_tool_ui_metadata_and_resources(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"profiles": {"lab": {"command": "python"}}}))
    client = BridgeClient(path, lock_path=tmp_path / "lock")
    calls = []

    async def request(profile, method, **kwargs):
        calls.append(method)
        if method == "tools":
            return {"tools": [{"name": "view", "inputSchema": {"type": "object"}, "_meta": {"ui": {"resourceUri": "ui://blender/view"}}}]}
        if method == "resources":
            return types.ListResourcesResult(resources=[types.Resource(uri="ui://blender/view", name="Blender", mimeType="text/html;profile=mcp-app")])
        if method == "read_resource":
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri="ui://blender/view", text="<html>view</html>", _meta={"ui": {"prefersBorder": True}})], _meta={"example": True})
        return types.CallToolResult(content=[types.ImageContent(type="image", mimeType="image/png", data="YWJj")], _meta={"ui": {"x": 1}})

    monkeypatch.setattr(client, "_request", request)
    server = make_server(client, "lab")
    async def exercise():
        listed = await server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method="tools/list"))
        assert listed.root.tools[0].meta["ui"]["resourceUri"] == "ui://blender/view"
        called = await server.request_handlers[types.CallToolRequest](types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(name="view", arguments={})))
        assert called.root.content[0].data == "YWJj"
        assert called.root.meta == {"ui": {"x": 1}}
        resources = await server.request_handlers[types.ListResourcesRequest](types.ListResourcesRequest(method="resources/list"))
        assert str(resources.root.resources[0].uri) == "ui://blender/view"
        resource = await server.request_handlers[types.ReadResourceRequest](types.ReadResourceRequest(method="resources/read", params=types.ReadResourceRequestParams(uri="ui://blender/view")))
        assert resource.root.meta == {"example": True}
        assert resource.root.contents[0].meta["ui"]["prefersBorder"] is True
    asyncio.run(exercise())
    assert calls == ["tools", "call", "resources", "read_resource"]


def test_persistent_session_keeps_upstream_cache_and_lock(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"profiles": {"lab": {"command": "python"}}}))
    client = BridgeClient(path, lock_path=tmp_path / "lock")
    events = []

    @asynccontextmanager
    async def transport(*args, **kwargs):
        events.append("spawn")
        try:
            yield "read", "write"
        finally:
            events.append("close")

    class Session:
        def __init__(self, *args):
            self.cache = None
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def initialize(self):
            events.append("initialize")
        async def list_tools(self, cursor=None):
            return SimpleNamespace(tools=[], nextCursor=None)
        async def call_tool(self, name, arguments):
            with pytest.raises(client_module.BridgeError):
                with client_module.writer_lock(client.lock_path):
                    pass
            if name == "viewport":
                self.cache = "snapshot-1"
            return types.CallToolResult(content=[types.TextContent(type="text", text=self.cache or "missing")])

    monkeypatch.setattr(client_module, "stdio_client", transport)
    monkeypatch.setattr(client_module, "ClientSession", Session)
    async def exercise():
        async with client.persistent("lab") as connected:
            await connected.list_tools("lab")
            await connected.call_tool_raw("lab", "viewport", {})
            picked = await connected.call_tool_raw("lab", "pick", {})
            assert picked.content[0].text == "snapshot-1"
            assert events == ["spawn", "initialize"]
            with client_module.writer_lock(client.lock_path):
                pass
        assert events == ["spawn", "initialize", "close"]
    asyncio.run(exercise())
