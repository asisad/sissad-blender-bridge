# Architecture

This independent project coordinates separately installed Blender integrations. It does not change the SketchUp project or its typed-only execution policy.

## Connection paths

```text
Codex local client -> MCP server (stdio) -> Blender add-on (loopback TCP) -> scene
CLI/API client -> bridge orchestration -> selected integration -> scene
ChatGPT Web -> authenticated Secure MCP Tunnel -> local MCP server -> add-on -> scene
```

The official Blender Lab and community MCP for Blender adapters are distinct installations. Keep their server identities, environments, configured ports and provenance separate. Discover tools from the running server; do not assume equal catalogues. One writer owns a Blender scene at a time. Parallel agents may inspect documentation and independent files, but scene mutations must be serialized.

## Version support

Discover the executable, build/version, active add-on and tools at connection time. Record compatibility per combination of Blender build and integration commit. A successful test of one version does not prove another. Unsupported API features should fail explicitly rather than silently change meaning. The compatibility targets for this work are Blender 5.2.2 and Blender 5.3 Beta; each requires separate evidence.

## Execution boundary

On 2026-10-11 the owner explicitly authorized arbitrary Python execution only for this independent Blender project. Such execution can access files, network and process capabilities available to Blender. Loopback binding, a separate repository, virtual environments and upstream safe modes are not operating-system sandboxes. See [SECURITY.md](../SECURITY.md).

Upstream code is installed separately, not bundled in this project. The orchestration layer should record lifecycle ownership, capability inventory, evidence, and operation outcomes. Retry only operations known to be safe to repeat; after a mutation timeout, inspect the scene before retrying.

## Evidence boundary

A registered MCP entry is not an end-to-end connection. A test-client success does not prove tools are available in the active chat. Streamable HTTP describes an MCP transport; it does not prove live viewport video or scene-event streaming.

Sources: [Blender Lab MCP](https://www.blender.org/lab/mcp-server/), [official source](https://projects.blender.org/lab/blender_mcp), [community source](https://github.com/ahujasid/mcp-for-blender), [Codex MCP](https://developers.openai.com/codex/mcp).
