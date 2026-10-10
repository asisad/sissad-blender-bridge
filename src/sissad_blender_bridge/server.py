"""Stdio proxy: preserve tool schemas, images, metadata and UI resources."""
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .client import BridgeClient, BridgeError, redact


def make_server(client: BridgeClient, profile: str, timeout: float = 300) -> Server:
    client.profile(profile)
    server = Server("sissad-blender-bridge", version="0.1.0")

    @server.list_tools()
    async def list_tools():
        result = await client.list_tools(profile, timeout=timeout)
        return [types.Tool.model_validate(tool) for tool in result["tools"]]

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        # Upstream performs schema validation; avoid echoing potentially sensitive
        # argument values in this proxy's validation errors.
        try:
            return await client.call_tool_raw(profile, name, arguments, timeout=timeout)
        except BridgeError as error:
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=f"{error.code}: {error}")])

    # Low-level handlers retain full result-level _meta and original resource URIs.
    async def resources(request):
        cursor = request.params.cursor if request.params else None
        result = await client._request(profile, "resources", arguments=cursor, timeout=timeout)
        return types.ServerResult(types.ListResourcesResult.model_validate(redact(result.model_dump(mode="json", by_alias=True, exclude_none=True))))

    async def read_resource(request):
        result = await client._request(profile, "read_resource", tool=request.params.uri, timeout=timeout)
        return types.ServerResult(types.ReadResourceResult.model_validate(redact(result.model_dump(mode="json", by_alias=True, exclude_none=True))))

    server.request_handlers[types.ListResourcesRequest] = resources
    server.request_handlers[types.ReadResourceRequest] = read_resource
    return server


async def serve(client: BridgeClient, profile: str, *, timeout: float = 300):
    async with client.persistent(profile, timeout=timeout) as connected:
        server = make_server(connected, profile, timeout)
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
