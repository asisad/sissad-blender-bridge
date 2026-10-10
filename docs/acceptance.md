# Acceptance protocol

This is the acceptance protocol, not evidence by itself. Actual results and coverage limits are in [the dated verification log](verification-2026-10-11.md). Use a fresh disposable scene and an explicit output directory. Never reset, close or overwrite a user's unsaved scene.

## Required checks

| Check | Required evidence |
|---|---|
| Runtime identity | Executable path, Blender version/build, integration commit/version, session identity |
| MCP | Successful initialize and tools/list, discovered schemas and server identity |
| CLI/API | Real request and structured response through the installed connection |
| Client to Blender | Create AI_Connection_Test, metric dimensions of one metre, reread dimensions from Blender |
| Blender to client | A known scene-side change appears in a subsequent client read; identify whether polling or events |
| Scoped material | Change only target material; unchanged geometry and transforms |
| Visual feedback | Actual viewport capture or render from that scene, opened and visually inspected |
| Save/reopen | Save test .blend, reopen in a separate controlled process, verify expected contents |
| Camera-only | Two camera views with unchanged protected geometry signatures |
| Lifecycle | Stop only owned server, restart, reconnect without unintended scene change |
| Failure recovery | Missing runtime, timeout and port conflict produce actionable errors; retries do not duplicate mutations |
| Active local chat | Actual tool invocation from the target local chat, separately from test harness evidence |
| Web chat | Actual read and test-object creation from the connected ChatGPT Web conversation |

## Compatibility matrix

Maintain separate rows for each tested Blender build and official/community integration commit. The dated log records four local passing combinations: Blender 5.2.2 / official, Blender 5.2.2 / community, Blender 5.3 Beta / official, Blender 5.3 Beta / community. Older and future versions are untested unless evidence is added. Do not infer compatibility from an installed manifest alone.

## Protected geometry comparison

At a fixed frame and unit system, collect a deterministic snapshot of non-camera objects: stable identifiers and types, parent relations, visibility, world transforms, mesh vertices and edge/loop/polygon topology, face material assignments, modifiers, constraints, shape keys, Geometry Nodes settings and evaluated geometry. Hash ordered normalized records. Vertex and face counts alone are insufficient. Declare numeric tolerances in the test record.

Only camera data, camera transforms and active-camera selection may differ in a camera-only test. Camera-dependent Geometry Nodes can legitimately change evaluated geometry; report failure or an explicit unsupported case instead of claiming protection. Post-execution comparison detects changes; it cannot sandbox arbitrary Python or guarantee prevention.

## Evidence record

Record timestamp, tested versions/commits, client identity, sanitized request/result, output paths and hashes, actual checks performed, failures and unresolved checks. Do not include credentials. Generated images from another model are not Blender evidence.

Use one final state: NOT_INSTALLED, INSTALLED_NOT_CONNECTED, LOCAL_CONNECTED_TESTED, WEB_CONNECTED_TESTED, or BLOCKED_WITH_EVIDENCE. Report partial coverage and blockers beside the state. Local success never implies web success.
