# Community status helper repair — 2026-10-23

## Observed failure

The existing `community52` MCP tool and a fresh local CLI request returned
`Error checking addon status: No module named 'blender_mcp.config'`.
Upstream `get_addon_status` catches the exception and returns ordinary text,
with `isError=false`; this was not a successful status check.

The pinned Community client (`mcp-for-blender` 2.1.9, commit
`7a0373ec9199183cb460068c4f96aed9c579fb4f`) imports the absent configuration
module inside `TelemetryCollector.__init__`, before checking its telemetry
opt-out environment variables. Both the pinned checkout and its installed
package omit that module.

## Repair boundary

The bridge's own Community child-launch adapter uses the configured executable's
sibling Python interpreter and `community_bootstrap.py`. When an explicit existing
upstream telemetry-disable flag is true **and** the configuration module is absent,
the bootstrap supplies only `telemetry_config.enabled=False`. An existing config
module is never shadowed. Without explicit opt-out, no substitute is installed
and the upstream missing-config error remains visible.

The cached existing proxy needed the same repair before it could reload our
launch adapter. A new owned `config.py` was therefore exclusively created in
the installed Community **client** package, from the tracked
`community_disabled_config.py`. It fails closed without the same explicit opt-out,
and exposes only `enabled=False`. Its source SHA-256 is
`83adc760ba6d4085791d6fdaa6b8f3d19d263bbd2f541c2c302d00b50ce7bc48`.
The deployment receipt is under ignored `.runtime/evidence/`.

No server tool implementation, installed Blender addon, upstream checkout,
Blender preference, consent value, credential, RAG data or design file changed.
The child receives the same host, port, safe-mode and privacy environment values.
The native upstream status helper still performs its handshake, integration
checks and real consent readback. A true consent value is not invented or changed.
The bridge adds no telemetry endpoint, authentication material, network sender
or unconditional success response.

## Verification

- Full bridge suite: **25 passed**. New regression coverage exercises the actual
  installed upstream status function with a controlled Blender connection,
  confirms missing-config failure without opt-out, real consent readback and
  unreachable consent `None`, an empty telemetry queue while disabled, and the
  unchanged Community safe-mode import rejection.
- Fresh existing `community52` CLI call: real native result, Blender `5.2.2 LTS`,
  addon `[1, 8]`, protocol `13` matching expected `13`, `up_to_date=true`,
  `telemetry_consent=false`, no premium generators enabled.
- Agent's fresh and root's independently checked cached actual Codex
  `community52.get_addon_status` calls: same successful native result after the
  scoped compatibility deployment. No Codex or Blender restart performed.
- `git diff --check`: passed. Pinned Community checkout remains clean.
- Offline wheel build: passed; archive inspection confirms both owned
  compatibility modules are included in `sissad_blender_bridge-0.1.0-py3-none-any.whl`.

An already-running proxy can retain old imported Python code and an upstream
child. The fresh CLI path loads the repair immediately; a downstream MCP
disconnect/reconnect replaces its proxy and child without restarting Blender or
Codex. The strictly disabled compatibility file resolves the same missing lazy
import for an already-running client, without requiring that reconnect. Calls
are never automatically replayed.

The two owned compatibility modules are inside the normal Python package;
the built wheel was inspected to confirm both are included. Fresh bridge launches apply the
bootstrap without a separate installation. For an already-running cached proxy,
the guarded, repeatable migration is:

```powershell
uv run python scripts/repair-community-status.py --config config.local.json --profile community52
```

It derives the client package from the existing configured interpreter, requires
the existing explicit opt-out, exclusively creates the missing file, and never
overwrites a real configuration. Repeating it reports an unchanged installation.
It does not restart processes or change consent or environment settings.

Tests use a unique ignored workspace `.audit-cache` directory because the host's
existing global pytest temp directory denied access. No ACL or security setting
was changed to run them. This verification covers the status helper on the
existing 5.2 connection; it is not a new compatibility claim for 5.3 or other builds.
