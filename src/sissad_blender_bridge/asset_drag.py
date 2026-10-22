"""Opt-in, one-gesture asset drop for a disposable Blender review scene.

Loaded on demand through the already authorized Blender adapter. This is not an
addon, OS input injector, or replacement for Blender's built-in drag handler.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import time

REVIEW_ASSETS = frozenset({
    'AAID_vanity_800', 'AAID_sofa_1800', 'AAID_side_table_450',
    'AAID_rain_shower_2100', 'AAID_pendant_320', 'AAID_mirror_oval_600x900',
    'AAID_lounge_chair_800', 'AAID_basin_500',
})


def verified_library(path, root, expected_hash):
    resolved = Path(path).resolve(strict=True)
    resolved.relative_to(Path(root).resolve(strict=True))
    if resolved.suffix.lower() != '.blend' or not resolved.is_file():
        raise ValueError('Expected a contained Blender library')
    if hashlib.sha256(resolved.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('Library content changed')
    return resolved


class Gesture:
    """Only a source press followed by a target release can commit once."""
    def __init__(self):
        self.pressed = False
        self.finished = False
        self.start = None

    def event(self, kind, value, source, target, position):
        if self.finished:
            return 'IGNORE'
        if kind in {'ESC', 'RIGHTMOUSE'}:
            self.finished = True
            return 'CANCEL'
        if kind != 'LEFTMOUSE':
            return 'CONSUME' if self.pressed else 'PASS'
        if value == 'PRESS':
            if not source or self.pressed:
                self.finished = True
                return 'CANCEL'
            self.pressed, self.start = True, position
            return 'CONSUME'
        if value == 'RELEASE' and self.pressed:
            self.finished = True
            distance = math.dist(self.start, position)
            return 'COMMIT' if target and distance >= 8 else 'CANCEL'
        return 'PASS'


_state = {'status': 'idle'}
_operator = None
_class = None


def _inside(region, event):
    return (region.x <= event.mouse_x < region.x + region.width and
            region.y <= event.mouse_y < region.y + region.height)


def arm(*, library_file, library_root, library_hash, asset_name, scene_name,
        allowed_assets, timeout=60):
    """Arm exactly the preselected collection in an explicitly marked QA scene."""
    import bpy
    global _state, _class
    if _state.get('status') == 'armed':
        raise RuntimeError('An asset gesture is already armed')
    cleanup()
    scene = bpy.context.scene
    window = bpy.context.window
    screen = window.screen
    if scene.name != scene_name or not scene.get('sissad_bridge_test_session'):
        raise ValueError('Only the explicitly marked disposable review scene is allowed')
    if (bpy.context.mode != 'OBJECT' or asset_name not in allowed_assets or
        asset_name not in REVIEW_ASSETS):
        raise ValueError('Expected an approved collection in Object Mode')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
        raise ValueError('Timeout must be between 1 and 120 seconds')
    library = verified_library(library_file, library_root, library_hash)
    if not any(Path(x.path).resolve() == Path(library_root).resolve()
               for x in bpy.context.preferences.filepaths.asset_libraries):
        raise ValueError('Library is not registered')
    source = next(a for a in window.screen.areas
                  if a.type == 'FILE_BROWSER' and a.ui_type == 'ASSETS')
    source_region = next(r for r in source.regions if r.type == 'WINDOW')
    view = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    view_region = next(r for r in view.regions if r.type == 'WINDOW')
    filepath = bpy.data.filepath

    def validate_asset(context):
        with context.temp_override(window=window, area=source, region=source_region):
            asset = bpy.context.asset
            if (not asset or asset.id_type != 'COLLECTION' or
                asset.name != asset_name or Path(asset.full_library_path).resolve() != library):
                raise ValueError('Selected asset changed')

    validate_asset(bpy.context)
    _state = {'status': 'armed', 'mode': 'bridge-assisted-mouse-drag',
              'asset': asset_name, 'scene': scene_name, 'events': []}

    class SISSAD_OT_review_asset_drag(bpy.types.Operator):
        bl_idname = 'sissad.review_asset_drag'
        bl_label = 'SiSsad Review Asset Drag'
        bl_options = {'INTERNAL'}

        def invoke(self, context, event):
            global _operator
            self.gesture = Gesture()
            self.started = time.monotonic()
            self.timer = context.window_manager.event_timer_add(.25, window=window)
            context.window_manager.modal_handler_add(self)
            _operator = self
            return {'RUNNING_MODAL'}

        def finish(self, context, status, **details):
            global _operator
            try:
                if self.timer:
                    context.window_manager.event_timer_remove(self.timer)
            except (ReferenceError, RuntimeError):
                details['timer_already_removed'] = True
            finally:
                self.timer = None
                _operator = None
                _state.update(status=status, **details)
            return {'FINISHED'} if status == 'imported' else {'CANCELLED'}

        def cancel(self, context):
            self.finish(context, 'cancelled', reason='Blender cancelled the operator')

        def modal(self, context, event):
            try:
                return self.step(context, event)
            except (ReferenceError, RuntimeError) as exc:
                return self.finish(context, 'cancelled', reason='Invalidated context: ' + str(exc))
            except Exception as exc:
                return self.finish(context, 'failed', reason=str(exc))

        def step(self, context, event):
            if (time.monotonic() - self.started > timeout or context.window != window or
                window.screen != screen or window.scene != scene or bpy.data.filepath != filepath or
                context.mode != 'OBJECT' or source not in list(screen.areas) or
                view not in list(screen.areas) or source.type != 'FILE_BROWSER' or
                source.ui_type != 'ASSETS' or view.type != 'VIEW_3D' or
                source_region not in list(source.regions) or view_region not in list(view.regions)):
                return self.finish(context, 'cancelled', reason='Context changed or timeout')
            if event.type == 'TIMER':
                return {'RUNNING_MODAL'}
            if len(_state['events']) < 24 and event.type in {'LEFTMOUSE', 'ESC', 'RIGHTMOUSE', 'MOUSEMOVE'}:
                _state['events'].append({'type': event.type, 'value': event.value,
                                        'x': event.mouse_x, 'y': event.mouse_y})
            source_hit, target_hit = _inside(source_region, event), _inside(view_region, event)
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                try:
                    if event.ctrl or event.shift or event.alt or event.oskey:
                        raise ValueError('Modified gesture')
                    validate_asset(context)
                    verified_library(library, library_root, library_hash)
                except Exception as exc:
                    return self.finish(context, 'cancelled', reason=str(exc))
            action = self.gesture.event(event.type, event.value, source_hit, target_hit,
                                        (event.mouse_x, event.mouse_y))
            if action == 'CANCEL':
                return self.finish(context, 'cancelled', reason='Gesture cancelled or outside target')
            if action == 'COMMIT':
                before = {o.as_pointer() for o in scene.objects}
                try:
                    from bpy_extras import view3d_utils
                    from mathutils import Vector
                    from mathutils.geometry import intersect_line_plane
                    coord = (event.mouse_x-view_region.x, event.mouse_y-view_region.y)
                    rv3d = view.spaces.active.region_3d
                    origin = view3d_utils.region_2d_to_origin_3d(view_region, rv3d, coord)
                    direction = view3d_utils.region_2d_to_vector_3d(view_region, rv3d, coord)
                    point = intersect_line_plane(origin, origin+direction, Vector((0,0,0)), Vector((0,0,1)))
                    if point is None or not all(math.isfinite(v) and abs(v) < 10000 for v in point):
                        raise ValueError('Invalid ground projection')
                    verified_library(library, library_root, library_hash)
                    with context.temp_override(window=window, area=view, region=view_region):
                        outcome = bpy.ops.wm.append(directory=str(library) + '/Collection/',
                                                    filename=asset_name, link=False,
                                                    instance_collections=True)
                    added = [o for o in scene.objects if o.as_pointer() not in before]
                    if (outcome != {'FINISHED'} or len(added) != 1 or added[0].type != 'EMPTY' or
                        added[0].instance_type != 'COLLECTION' or not added[0].instance_collection or
                        not added[0].instance_collection.name.startswith(asset_name) or
                        not any(o.type == 'MESH' and len(o.data.vertices)
                                for o in added[0].instance_collection.all_objects)):
                        raise RuntimeError('Native append did not produce exactly one collection instance')
                    obj = added[0]
                    obj.location = point
                    context.view_layer.update()
                    return self.finish(context, 'imported', object=obj.name,
                                       collection=obj.instance_collection.name,
                                       location=list(obj.location), added_count=len(added))
                except Exception as exc:
                    # Only objects created by this one append may be removed.
                    # Keep any newly loaded orphan datablocks; never globally undo.
                    added = [o for o in scene.objects if o.as_pointer() not in before]
                    removed = []
                    try:
                        for obj in added:
                            removed.append(obj.name)
                            bpy.data.objects.remove(obj, do_unlink=True)
                    except Exception as rollback:
                        return self.finish(context, 'failed', reason=str(exc),
                                           partial_mutation=True, rollback_error=str(rollback))
                    return self.finish(context, 'failed', reason=str(exc),
                                       rollback_removed_objects=removed,
                                       loaded_orphan_datablocks_may_remain=bool(removed),
                                       partial_scene_mutation=False)
            return {'PASS_THROUGH'} if action == 'PASS' else {'RUNNING_MODAL'}

    _class = SISSAD_OT_review_asset_drag
    bpy.utils.register_class(_class)
    bpy.ops.sissad.review_asset_drag('INVOKE_DEFAULT')
    return dict(_state)


def status():
    return dict(_state)


def cleanup():
    import bpy
    global _class
    if _operator is not None:
        raise RuntimeError('Cancel the active gesture or wait for its timeout before cleanup')
    if _class is not None:
        bpy.utils.unregister_class(_class)
        _class = None
