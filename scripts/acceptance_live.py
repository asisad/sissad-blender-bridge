"""Live acceptance on explicitly marked disposable Blender GUI scenes only.

Run: uv run python scripts/acceptance_live.py --profiles lab52 community52 lab53 community53
Never retries mutations. `ok` requires returned assertions, geometry invariants,
and actual image/blend files; text-only upstream success flags are insufficient.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys

from sissad_blender_bridge import BridgeClient

GUARD = """import bpy
import json
assert bpy.context.scene.get('sissad_bridge_test_session') is True, 'Disposable test scene marker required'
scene = bpy.context.scene
"""
SNAPSHOT = """
bpy.context.view_layer.update()
obj = bpy.data.objects['AI_Connection_Test']
result = {'acceptance_marker': 'sissad-live-v1', 'version': bpy.app.version_string,
          'dimensions': list(obj.dimensions), 'vertices': [list(v.co) for v in obj.data.vertices],
          'polygons': [list(p.vertices) for p in obj.data.polygons],
          'matrix': [list(row) for row in obj.matrix_world],
          'file': bpy.data.filepath, 'material': [m.name for m in obj.data.materials]}
assert all(abs(d - 1.0) < 0.00001 for d in obj.dimensions), 'Cube must measure one metre'
print('SISSAD_ACCEPTANCE_JSON=' + json.dumps(result))
"""


def extract(payload):
    if isinstance(payload, dict):
        if payload.get('acceptance_marker') == 'sissad-live-v1':
            return payload
        for value in payload.values():
            found = extract(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = extract(value)
            if found:
                return found
    if isinstance(payload, str):
        for line in payload.splitlines():
            if 'SISSAD_ACCEPTANCE_JSON=' in line:
                try:
                    return json.loads(line.split('SISSAD_ACCEPTANCE_JSON=', 1)[1])
                except ValueError:
                    pass
        try:
            nested = json.loads(payload)
            if isinstance(nested, (dict, list)):
                return extract(nested)
        except ValueError:
            pass
    return None


def geometry_hash(snapshot):
    selected = {key: snapshot[key] for key in ('vertices', 'polygons', 'matrix')}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


async def acceptance(client, profile, directory):
    record = {'profile': profile, 'passed': False, 'stages': []}
    try:
        tools = await client.list_tools(profile)
        (directory / f'{profile}-tools.json').write_text(json.dumps(tools, indent=2), encoding='utf-8')
        assert any(t['name'] == 'execute_blender_code' for t in tools['tools'])

        async def stage(name, body):
            result = await client.call_tool(profile, 'execute_blender_code', {'code': GUARD + body + SNAPSHOT}, timeout=300)
            (directory / f'{profile}-{name}-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            assert not result.get('isError'), f'{name}: upstream MCP error'
            snapshot = extract(result)
            assert snapshot, f'{name}: no validated acceptance payload; inspect result evidence'
            record['stages'].append({'name': name, 'snapshot': snapshot, 'geometry_sha256': geometry_hash(snapshot)})
            print(f'{profile}: {name} verified', flush=True)
            return snapshot

        initial = await stage('create', """
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
obj = bpy.data.objects.get('AI_Connection_Test')
if obj is None:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = 'AI_Connection_Test'
obj.dimensions = (1.0, 1.0, 1.0)
for other in scene.objects:
    if other.type == 'MESH':
        other.hide_render = other.name != 'AI_Connection_Test'
""")
        material = await stage('material', """
obj = bpy.data.objects['AI_Connection_Test']
mat = bpy.data.materials.get('AI_Connection_Test_Material')
if mat is None:
    mat = bpy.data.materials.new('AI_Connection_Test_Material')
mat.diffuse_color = (0.035, 0.4, 0.65, 1.0)
obj.data.materials.clear()
obj.data.materials.append(mat)
""")
        assert geometry_hash(initial) == geometry_hash(material), 'Material changed geometry or matrix'
        for index, position in enumerate(((2.8, -3.4, 2.5), (-3.2, -2.4, 1.8)), 1):
            output = directory / f'{profile}-view{index}.png'
            snapshot = await stage(f'camera{index}', f"""
from mathutils import Vector
camera = bpy.data.objects.get('AI_Connection_Test_Camera')
if camera is None:
    data = bpy.data.cameras.new('AI_Connection_Test_Camera')
    camera = bpy.data.objects.new('AI_Connection_Test_Camera', data)
    scene.collection.objects.link(camera)
camera.location = {position!r}
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 2.8
scene.camera = camera
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'MATERIAL'
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.background_type = 'WORLD'
scene.world.color = (0.08, 0.08, 0.08)
scene.render.resolution_x = 800
scene.render.resolution_y = 600
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = {str(output)!r}
bpy.ops.render.render(write_still=True)
""")
            assert geometry_hash(snapshot) == geometry_hash(initial), 'Camera changed geometry or matrix'
            assert output.is_file() and output.stat().st_size > 1000, 'Missing rendered image'
        blend = directory / f'{profile}-acceptance.blend'
        await stage('save', f"bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r})\n")
        reread = await stage('readback', '')
        assert geometry_hash(reread) == geometry_hash(initial)
        assert Path(reread['file']).resolve() == blend
        assert blend.is_file() and blend.stat().st_size > 1000
        record['passed'] = True
    except Exception as error:
        record['error'] = f'{type(error).__name__}: {error}'
        print(f'{profile}: FAILED: {record["error"]}', flush=True)
    (directory / f'{profile}-acceptance.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


async def run(options):
    root = Path(__file__).resolve().parents[1]
    directory = (root / '.runtime' / 'evidence').resolve()
    directory.mkdir(parents=True, exist_ok=True)
    client = BridgeClient(options.config or root / 'config.local.json')
    results = []
    for profile in options.profiles:
        results.append(await acceptance(client, profile, directory))
    (directory / 'acceptance-summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0 if all(item['passed'] for item in results) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--profiles', nargs='+', default=['lab52', 'community52', 'lab53', 'community53'])
    sys.exit(asyncio.run(run(parser.parse_args())))
