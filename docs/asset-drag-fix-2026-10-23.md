# Selected-asset mouse transfer repair — 2026-10-23

Historical fallback only. The completed ordinary Windows mouse drag repair is
documented in [native-mouse-fix-2026-10-23.md](native-mouse-fix-2026-10-23.md).
The Append-based helper below was not used for the final native mouse acceptance.

The existing native Asset Browser drag was inconsistent under the installed
Windows Computer Use gesture. Native event inspection showed a source press,
one large move directly into the 3D view, and release. Repeated stock drags
often imported nothing. This evidence does not prove a general Blender bug.

The owned `asset_drag.py` module provides an explicitly armed, bridge-assisted
selected-asset transfer gesture. It consumes the real mouse press/move/release,
then calls Blender's native Append on a valid release in the 3D view. It does
not inject OS input, imitate success, install an addon or patch Blender's own
drag handler. The actual Windows gesture still comes from supported Computer Use.

## Scope and safeguards

- Only the eight named AAID collection assets in `REVIEW_ASSETS` are accepted.
- A registered library root, resolved contained `.blend` and explicit SHA-256
  must match on arm, press and release. Changing file content cancels the import.
- Only an explicitly named review scene carrying
  `sissad_bridge_test_session=True`, in Object Mode, is eligible. No scene is
  created or marked automatically by this helper.
- Preselect the approved asset before arming. The source is the Asset Browser
  WINDOW region, not a screenshot tile hit test: while armed, dragging from
  blank space in that region also transfers the **preselected** asset. This is
  a selected-asset gesture, not a replacement for native thumbnail hit testing.
- Only release in the captured 3D WINDOW region can commit once. A ground-plane
  ray determines placement. Nonfinite, parallel and extreme projections fail.
- Outside release, Escape/right click, changed scene/screen/editor/file/mode,
  invalidated region or timeout cancels. Only the helper's own timer is removed.
  Cleanup unregisters only its own completed modal class.
- Native append must produce exactly one new collection instance with mesh
  geometry. On a failed append/validation only newly created scene objects are
  removed; newly loaded orphan datablocks may remain and are reported. Existing
  objects are never globally undone or removed.
- No input preferences are saved. Installed addon source, design masters, RAG,
  credentials and tunnel configuration remain unchanged.

## Reusable local procedure

From the existing bridge checkout/environment, preselect the desired collection
in the visible Asset Browser, inspect the current window, then arm:

```powershell
uv run python scripts/asset-drag.py --profile lab52 arm `
  --scene AAID_Closure_AssetDrag_Test --asset AAID_side_table_450 `
  --root '<registered library directory>' `
  --library '<registered library directory>\AAID_Interior_Assets.blend' `
  --sha256 '<approved library SHA-256>'
```

Execute one supported Computer Use `drag` from the observed selected asset into
the observed 3D view. Inspect the resulting screenshot, then query:

```powershell
uv run python scripts/asset-drag.py --profile lab52 status
uv run python scripts/asset-drag.py --profile lab52 cleanup
```

Every transfer is armed separately. After Blender restarts, the same command
loads the owned helper on demand again. It does not save startup preferences or
start another bridge service. A still-active gesture must first be cancelled
or allowed to time out before cleanup. Do not blindly repeat a dispatched drag:
read the result and scene first. The CLI checks the actual Lab result envelope,
not just MCP's `isError` flag.

## Live evidence

On the existing Blender **5.2.2 LTS**, disposable scene
`AAID_Closure_AssetDrag_Test`:

1. Real supported mouse drag imported `AAID_side_table_450` at approximately
   `(-0.69103, -0.73646, 0)`: scene instances **2 → 3**.
2. A separately armed real mouse drag imported `AAID_side_table_450.001` at
   `(-2.41595, -1.24389, 0)`: **3 → 4**.
3. A real drag released outside the 3D region cancelled: **4 → 4**.
4. The final guarded module was armed through the local CLI; changing the
   active scene cancelled it without importing: **4 → 4**. Cleanup succeeded.
5. Independent actual Community MCP and ChatGPT Web bridge reads returned both
   imported instances, identical positions, each with **4 meshes / 302 vertices**.
   The previous instances' matrices remained unchanged.
6. Native screenshots were inspected. Original input settings were restored:
   immediate drag `True`, mouse threshold `3`, general threshold `30`.

Private JSON event traces, independent readbacks, image and fresh native review
copy are recorded in the existing closure output folder, outside Git.
This covers this bridge-assisted collection transfer on this Blender 5.2 session;
it does not certify stock drag behavior, material drops or other Blender versions.
