"""Blender-side read-only verification of an acceptance file."""
import json
import bpy

obj = bpy.data.objects.get('AI_Connection_Test')
assert obj is not None and obj.type == 'MESH'
assert all(abs(value - 1.0) < 0.00001 for value in obj.dimensions)
assert len(obj.data.vertices) == 8
assert bpy.context.scene.get('sissad_bridge_test_session') is True
print('SISSAD_REOPEN=' + json.dumps({'version': bpy.app.version_string, 'dimensions': list(obj.dimensions), 'vertices': len(obj.data.vertices)}))
