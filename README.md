# SiSsad Blender Bridge

Python API, CLI and MCP proxy for **Blender Lab MCP** and the independent
**MCP for Blender** project. The upstream tools run separately, on dedicated
loopback ports; this project does not reimplement or bundle their add-ons.

[راهنمای فارسی](README.fa.md) · [Windows setup](docs/install-windows.md) ·
[Compatibility](docs/compatibility.md) · [Security](SECURITY.md)

**Verified on 2026-10-11:** four local provider/version combinations on Blender
5.2.2 LTS and 5.3 Beta; a real ChatGPT Web write and separate readback on Lab 5.2.
See [exact results and coverage limits](docs/verification-2026-10-11.md).

## What this delivers

- Four explicit profiles: `lab52`, `community52`, `lab53`, `community53`.
- Both upstream providers can address the same Blender session sequentially.
- A shared process lock serializes calls made through this bridge.
- A persistent MCP proxy preserves tool metadata, image results and UI resources.
- A reusable Python client and JSON CLI, pinned upstream revisions and dependencies.
- Disposable-scene acceptance with real renders, material-only changes, geometry
  checks, `.blend` saves and readback. See the dated verification log for results.
- Version/plugin capability inventory and explicit untested status. Supporting
  an API is not proof that every plug-in or future Blender version works.

## Quick start (Windows)

Install Blender, Git, uv, then clone this repository. In PowerShell:

```powershell
.\scripts\setup.ps1 -Blender52 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
.\scripts\start-blender.ps1 -Version 52 -BlenderPath 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -TestScene -Visible
uv run sissad-blender --config config.local.json tools --profile lab52
uv run python scripts/acceptance_live.py --profiles lab52 community52
.\scripts\register-codex.ps1
```

Pass `-Blender53 '<absolute path to the Blender 5.3 executable>'` to setup for
the second installation. The public scripts currently support the 5.2/5.3
installation layout; arbitrary additional versions require a new tested profile.

The Codex registration creates a local plugin using the installed absolute paths.
A client restart may be required to discover newly registered tools. It does not
restart Codex or close an existing Blender project automatically.

## CLI and Python API

```powershell
uv run sissad-blender --config config.local.json profiles
uv run sissad-blender --config config.local.json doctor
uv run sissad-blender --config config.local.json call --profile lab52 --tool execute_blender_code --arguments-file request.json
uv run sissad-blender --config config.local.json serve --profile community52
```

`request.json` contains the discovered tool's arguments, for example
`{"code":"import bpy; result = {'version': bpy.app.version_string}"}` for Lab.
For Community, print JSON to return it; inspect tool schemas instead of assuming
that similarly named tools have identical response formats.

```python
import asyncio
from sissad_blender_bridge import BridgeClient

async def inspect():
    bridge = BridgeClient('config.local.json')
    return await bridge.call_tool('lab52', 'execute_blender_code', {
        'code': "import bpy; result = {'version': bpy.app.version_string}"
    })

print(asyncio.run(inspect()))
```

`ok` reports MCP status, not the semantic success of a Blender edit. Some upstream
tools return error text without setting `isError`; verify the returned scene data.
Timeouts never automatically replay a dispatched write.

## ChatGPT Web

Use the official Secure MCP Tunnel, with a dedicated tunnel and runtime key.
`scripts/connect-web.ps1` attaches an existing tunnel; it never reuses another
integration's credentials or creates a public raw Blender port. See
[the web procedure](docs/web-connection.md). A local test is not a web test.

## Security and release boundaries

Both upstream projects can execute Python in Blender. Loopback, a virtual
environment and Community Safe Mode are **not a sandbox**. The exception granted
for this independent project does not alter the sibling SketchUp project.
The local socket services do not authenticate callers; trusted-local-process
access is a residual risk. Paid asset services are not enabled by setup.

Upstream code is downloaded from pinned revisions into ignored `.runtime/` and
installed separately. Licenses and provenance are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
No private Blender scenes, credentials, user preferences or local configuration
belong in a public commit.

## Development

```powershell
uv sync --frozen
uv run pytest --basetemp .runtime/pytest -q
uv build
git diff --check
```

Blender live tests require owned, explicitly marked disposable GUI sessions.
CI unit tests alone cannot validate live Blender, GPU rendering or ChatGPT Web.
