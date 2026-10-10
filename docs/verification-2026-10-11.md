# Verification log — 2026-10-11

Milestone: independent Blender bridge 0.1.0. Local state:
**LOCAL_CONNECTED_TESTED** through Python API, CLI and the stdio MCP proxy.
No existing production scene was used. Tests ran in explicitly marked disposable
GUI sessions. Exact upstream revisions and licenses: [compatibility](compatibility.md).

| Build | Provider | Six local stages | Independent reopen |
|---|---|---|---|
| 5.2.2 LTS, `d13f752e3b9c` | Lab 1.0.2 | Pass | Pass |
| 5.2.2 LTS, `d13f752e3b9c` | Community 2.1.9 | Pass | Pass |
| 5.3.0 Beta, `c53a881a51a1` | Lab 1.0.2 | Pass | Pass |
| 5.3.0 Beta, `c53a881a51a1` | Community 2.1.9 | Pass | Pass |

The six stages were create, material change, first camera, second camera, save
and readback. Each created a 1 m cube named `AI_Connection_Test`. Geometry checks
compared that cube's vertex coordinates, polygon topology and world matrix.
This is intentionally narrower than the comprehensive production-scene snapshot
specified by the protocol; modifiers, shape keys and arbitrary scene dependencies
are not covered by this fixture.

Eight real Blender Workbench renders (800 x 600) were produced and inspected.
Four saved `.blend` files were reopened in independent background processes with
auto-execution disabled, confirming dimensions, eight vertices and the test marker.
Only synthetic example renders are included publicly; raw files, logs and
inventories remain in the ignored local evidence directory.

Additional checks:

- MCP initialize and tools/list: 26 Lab tools and 14 Community tools.
- A Blender timer changed a scene-side marker; the client observed it on a later
  read. This verifies polling in the reverse direction, not push/video streaming.
- Proxy/upstream process disconnect and reconnect preserved the test geometry.
- Community `look` returned actual image content. Its viewport UI resource was
  listed and read through the proxy. Rendering that interactive UI inside the
  current Codex panel has not been verified.
- Capability inventories found 2,511 operators in 5.2 and 2,569 in 5.3. Discovery
  is not execution coverage for those operators or every installed add-on.
- 16 unit tests passed, including cross-process locking, timeout/error handling,
  configuration rejection and metadata/resource forwarding. PowerShell scripts
  passed parser checks. Source and wheel builds succeeded.
- The local Codex plugin was installed with four profiles. This running chat has
  not hot-loaded those native tool bindings; reopen/restart and perform an actual
  native tool invocation before marking that particular surface verified.

## Web work

A dedicated Secure MCP Tunnel and a restricted runtime key (Tunnels Read + Use)
were created. The key stays outside the repository, encrypted with Windows DPAPI
and protected by a local ACL. The managed tunnel runtime reports healthy and ready.
The dedicated ChatGPT plugin is installed and visibly Connected.

**WEB_CONNECTED_TESTED — Lab / Blender 5.2.2 LTS.** A real ChatGPT Web conversation
read the version and disposable-scene marker, created a new 1 m cube named
`AI_Web_Connection_Test` at `(3, 0, 0)`, and set its `sissad_web_probe` property to
`web-20261011`. A separate web tool invocation reread the object and reported
`verification_passed: true`. An independent local CLI read confirmed the same
name, dimensions, location and property. No save/overwrite call was made by the
web test. Account identifiers, conversation URLs and browser screenshots remain
private. A sanitized local confirmation is in `evidence/web-readback.json`.

The web test covered the Lab 5.2 profile. Other profiles passed locally; their
individual ChatGPT Web invocation and interactive UI rendering remain untested.

## Corrections found by testing

- Separate ports are required because the two upstreams use different protocols
  but default to the same port.
- Factory startup needs explicit add-on preference registration.
- Reinstall must reload copied modules rather than retaining old imports.
- The current Community image tool is `look`; the earlier screenshot tool name
  is obsolete for the pinned version.
- Tunnel command parsing on Windows consumes backslashes. Quoted forward-slash
  paths fix process startup; the connector now checks actual health/readiness.
- The first clean CI checkout lacked the ignored `.runtime` parent needed by
  pytest's explicit temporary directory. CI and development instructions now
  create that parent before running tests.

## Remaining scope boundaries

Older/future versions, arbitrary third-party plug-ins, production interior,
jewelry, avatar and game workflows require their own fixtures. No claim of
universal version compatibility, plugin mastery, sandboxing or lossless streaming
is made. Both upstream raw sockets remain on loopback but lack authentication.
The tunnel authenticates the web boundary; it does not sandbox Blender Python.

Reproduce with `scripts/acceptance_live.py`, `scripts/verify_roundtrip.py`,
`scripts/inventory_blender.py` and `scripts/watch_scene.py`. Inspect prerequisites
and disposable-scene guards before running mutation tests.
