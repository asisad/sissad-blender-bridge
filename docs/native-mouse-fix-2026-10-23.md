# Ordinary Blender mouse drag — verified 2026-10-23

The ordinary Asset Browser collection drop succeeded four consecutive times in
Blender **5.2.2 LTS** using normal Windows mouse input. This supersedes the earlier
[Append-based fallback](asset-drag-fix-2026-10-23.md) for this acceptance scope.
The status-helper repair is in the preceding commit, `15dbf4a`.

## Cause and repair

The installed Computer Use drag provided a press, one large move across editors,
and release. Native Blender starts its asset drag after movement inside the source
region; crossing editors immediately did not reliably start that operation.
The new local driver holds the button, makes a source-internal movement first,
then moves in steps to the viewport and releases. It does not import assets via
Python, invoke the drop operator, or install a Blender handler.

The user explicitly approved this **Blender-only local CLI input exception**.
The implementation uses Windows `SendInput` without elevation, hooks, services,
security changes, or input into another application. Blender's event-simulation
mode is rejected: a diagnostic simulation is not ordinary mouse acceptance.

Relevant primary source: Blender's [interface drag handling](https://github.com/blender/blender/blob/v5.2.2/source/blender/editors/interface/interface_handlers.cc)
and [event dispatch](https://github.com/blender/blender/blob/v5.2.2/source/blender/windowmanager/intern/wm_event_system.cc).
No Blender source was copied into this implementation.

## Procedure

Use the existing local Lab connection and an explicitly marked disposable review
scene, with Asset Browser and 3D viewport visible. Inspect a current screenshot.
Choose a source point over a collection asset, a waypoint still inside its source
region at least eight screenshot pixels away, and a viewport target. Coordinates
and screenshot size are observation-specific; never reuse an old layout blindly.

```powershell
python scripts/native-drag.py --profile lab52 --exe '<installed Blender path>\blender.exe' --scene '<marked review scene>' --asset '<collection asset name>' --source 835,576 --via 850,552 --target 650,450 --screenshot-size 1440,852
```

The default is a preflight dry run. Add `--execute` only with authorization for
local mouse input, and `--evidence '<new JSON path>'` to record before/after data.
The PID is read from the live connection; optional `--pid` also pins its expected
identity. No specific Blender version or PID is hard-coded in the driver.

The shared bridge writer lock covers snapshot, preflight, gesture, settling and
readback. The driver checks the executable path, PID, unique window, foreground,
unchanged window/client geometry, pointer coverage and Escape before input. It
rejects an already-held left button and releases its own press in `finally`.
The CLI requires Object Mode, the exact marked scene, valid editor regions, no
modal operators and no earlier custom asset-transfer helper. No automatic replay
occurs after a failure. Existing evidence files cannot be overwritten.

A desktop that cannot activate the selected Blender window is refused before
input. Inspect the interactive desktop and take a fresh screenshot before retrying;
the driver does not bypass a focus restriction or access barrier.

## Actual acceptance

Normal GUI process, `bpy.app.use_event_simulate=False`, scene
`AAID_Physical_Mouse_Proof_20261023`, with no custom transfer helper:

| Trial | Collection | Scene instances | Native operator |
| --- | --- | --- | --- |
| 1 | `AAID_side_table_450` | 0 → 1 | `OBJECT_OT_collection_external_asset_drop` |
| 2 | `AAID_lounge_chair_800` | 1 → 2 | same |
| 3 | `AAID_sofa_1800` | 2 → 3 | same |
| 4 | `AAID_side_table_450` | 3 → 4 | same |

Each trial added exactly one collection instance with real geometry; previous
instance matrices stayed unchanged. The result contains **28 meshes / 7,568
vertices** across four instances. Independent Lab, Community and actual ChatGPT
Web reads confirmed the same saved review file and four native drop operators.
The actual Blender window and Asset Browser were inspected; a native framebuffer
screenshot and a fresh `.blend` are stored privately with the four event records.
An invalid viewport target was rejected before input and left the count at four.

After review, the shared transaction lock and window-geometry guards were added.
The final **42 tests passed**, including concurrent-writer exclusion, geometry
change rejection and button release on interrupted input. A later dry run refused
window activation before dispatch; it did not replay or change the proven scene.
The final fixed read-only probes still confirmed all four native imports.

The actual `get_addon_status` returned `source=native`, protocol `13`, addon
`[1,8]`, `up_to_date=true`, `warning=null`, telemetry consent `false`. One stale
connection after switching the test GUI failed, then a fresh read-only request
reconnected successfully. No mutating request was replayed.

This proves ordinary collection drops for the tested Windows/Blender session.
Other versions, material drops, every plugin and final photoreal render quality
are separate claims. Original designs, addon sources and RAG remain protected.
Private scenes, local paths, credentials and full runtime traces are excluded
from the public repository.
