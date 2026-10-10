# Compatibility and upstream boundaries

Source review date: 2026-10-11. These declarations describe pinned upstream requirements, not a claim that all supported versions or tools were exercised.

| Integration | Pinned revision | Server / add-on | Declared minimum Blender | License |
|---|---|---|---|---|
| Blender Lab MCP | `dbbf836ad4b1025f14a2b3b504c43903f39e0b04` | `1.0.2` / `1.0.0` | `5.1.0` in extension manifest | GPL-3.0-or-later |
| MCP for Blender (community) | `7a0373ec9199183cb460068c4f96aed9c579fb4f` | `2.1.9` package | `3.0` in README prerequisites | MIT |

Primary sources: [Lab repository](https://projects.blender.org/lab/blender_mcp), [community repository](https://github.com/ahujasid/mcp-for-blender). Versions and license declarations were checked against the local pinned checkouts, including the Lab manifest, both package metadata files and licenses. This community project is independent of the Blender Foundation.

## Coexistence

Both upstreams default to TCP port 9876 and use different wire protocols. They cannot share the same endpoint. This installation allocates four loopback endpoints:

| Blender profile | Lab | Community |
|---|---|---|
| 5.2.2 LTS | `127.0.0.1:9876` | `127.0.0.1:9877` |
| 5.3.0 Beta | `127.0.0.1:9886` | `127.0.0.1:9887` |

Each upstream server has its own virtual environment and MCP profile. The Lab package is named `blender-mcp`, while the current community package is `mcp-for-blender`; avoid historical aliases and unpinned installation by name. One writer must own a scene at a time, even though both connections can read it. Parallel agents may research or inspect independently; they must not submit overlapping scene edits.

The observed installed Blender builds are 5.2.2 LTS (`d13f752e3b9c`) and 5.3.0 Beta (`c53a881a51a1`). A matching minimum version is not live proof. Consult dated acceptance evidence for the actual requests, images and pass/fail results. Older versions need a separate profile and tests. In particular, the current Lab add-on does not declare support below 5.1; the community minimum alone does not prove compatibility with every release since 3.0. Future Blender releases and third-party plugins remain untested.

## Lifecycle and modes

Lab supports GUI timers and a separate blocking background command (`blender --background file.blend --command blender_mcp`); deferred responses are unavailable in the latter. The community add-on explicitly refuses background mode because its command queue requires GUI timer servicing. Therefore a shared session with both integrations uses Blender GUI mode. Lab's delayed autostart checks whether its server already runs before starting again. Community's `start()` catches socket bind failures and returns; callers must verify its running state and actual connectivity before declaring readiness.

Lab reads `BLENDER_MCP_HOST` / `BLENDER_MCP_PORT`; community reads `BLENDER_HOST` / `BLENDER_PORT`. A TCP listener or a bootstrap marker alone is not adequate acceptance evidence: initialize MCP, list tools and execute a read against the intended Blender instance. Community stores its port on the scene, so opening a different file deserves a fresh connection check.

## Execution and plugin support

Both upstreams expose Python execution. The user authorized this specifically for the independent local Blender connection; it does not alter the sibling SketchUp project's typed allow-list rules. Lab's `weak_sandbox.py` explicitly describes its checks as guidance that can be worked around. Community safe mode validates submitted scripts but does not turn the raw add-on socket into an authenticated sandbox. The raw Blender services must stay on literal loopback; a web-facing transport needs its own authenticated boundary and an actual web-client test.

Blender Python can inspect installed add-ons and invoke available APIs and operators, but it cannot guarantee that every plugin has a stable automation API, license, suitable context or compatible binary dependencies. Discover capabilities per version and plugin, retain the returned tool schemas, then test the intended operation. UI/viewport tools may be advertised depending on MCP client capabilities or explicit community environment flags; advertisement does not prove that a particular client renders those tools correctly.

## Source pointers for maintenance

### Adding a different Blender version

The Python client and proxy do not hard-code Blender versions. Add a named entry
to the `profiles` map in the private configuration, with `command`, `args` and
`env` pointing to the chosen upstream server and that installation's dedicated
loopback port. Use safe names such as `community_older` or `lab_preview`.
Codex registration and the tunnel connector accept these configured names.
Check the installed add-on's actual minimum version first; below Lab's declared
5.1 minimum, evaluate a compatible community release separately.

The bundled automatic installer and four-profile acceptance fixture target
5.2/5.3. For other builds, install the selected upstream add-on using that build's
documented extension procedure, then discover tools and run a disposable-scene
test before production use. Never label a future version supported merely because
the transport connected. Pin any changed upstream revision and dependencies and
record its separate license and test results.

- Lab: `addon/blender_mcp_addon/blender_manifest.toml`; `mcp/pyproject.toml`; `addon/blender_mcp_addon/__init__.py` (autostart); `cli.py` (background mode); `mcp_to_blender_server.py` (request framing and execution); `weak_sandbox.py`.
- Community: `README.md` (minimum versions and unauthenticated socket warning); `pyproject.toml`; `addon.py` (`_blendermcp_ensure_server_running`, `BlenderMCPServer.start`, script execution); `LICENSE`.
