"""Read-only runtime/add-on/operator inventory; no preferences or scene contents."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from sissad_blender_bridge import BridgeClient

MARKER = 'sissad-inventory-v1'
CODE = '''import bpy
import addon_utils
import json
enabled = sorted(bpy.context.preferences.addons.keys())
addons = []
for module in addon_utils.modules(refresh=False):
    info = getattr(module, 'bl_info', {})
    addons.append({'module': module.__name__, 'name': str(info.get('name', module.__name__)),
                   'version': list(info.get('version', ())),
                   'blender_minimum': list(info.get('blender', ())),
                   'category': str(info.get('category', '')),
                   'enabled': module.__name__ in enabled,
                   'extension_namespace': module.__name__.startswith('bl_ext.')})
operators = []
for category in sorted(name for name in dir(bpy.ops) if not name.startswith('_')):
    names = sorted(name for name in dir(getattr(bpy.ops, category)) if not name.startswith('_'))
    operators.append({'category': category, 'count': len(names), 'operators': names})
engine_items = bpy.context.scene.render.bl_rna.properties['engine'].enum_items
engines = [{'identifier': item.identifier, 'name': item.name} for item in engine_items]
build_hash = bpy.app.build_hash
if isinstance(build_hash, bytes):
    build_hash = build_hash.decode('ascii', errors='replace')
result = {'inventory_marker': 'sissad-inventory-v1', 'version': list(bpy.app.version),
          'version_string': bpy.app.version_string, 'build_hash': str(build_hash),
          'enabled_addons': enabled, 'addons': sorted(addons, key=lambda item: item['module']),
          'operator_categories': operators, 'operator_count': sum(item['count'] for item in operators),
          'render_engines': engines, 'scope': 'metadata_only; operators_not_invoked; compatibility_not_proven'}
print('SISSAD_INVENTORY_JSON=' + json.dumps(result))
'''


def extract(payload):
    if isinstance(payload, dict):
        if payload.get('inventory_marker') == MARKER:
            return payload
        values = payload.values()
    elif isinstance(payload, list):
        values = payload
    elif isinstance(payload, str):
        for line in payload.splitlines():
            if line.startswith('SISSAD_INVENTORY_JSON='):
                try:
                    found = extract(json.loads(line.split('=', 1)[1]))
                    if found is not None:
                        return found
                except ValueError:
                    pass
        try:
            nested = json.loads(payload)
        except ValueError:
            return None
        return extract(nested) if isinstance(nested, (dict, list)) else None
    else:
        return None
    for value in values:
        found = extract(value)
        if found is not None:
            return found
    return None


async def run(options):
    client = BridgeClient(options.config)
    async with client.persistent(options.profile) as session:
        response = await session.call_tool(options.profile, 'execute_blender_code', {'code': CODE})
    if response.get('isError'):
        raise RuntimeError('Inventory tool returned an error; no successful inventory was saved.')
    result = extract(response)
    if result is None:
        raise RuntimeError('Inventory response did not contain the expected marker.')
    result['profile'] = options.profile
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding='utf-8')
    print(json.dumps({'ok': True, 'profile': options.profile, 'output': str(options.output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.local.json')
    parser.add_argument('--profile', default='lab52')
    parser.add_argument('--output', type=Path, default=Path('.runtime/evidence/inventory-lab52.json'))
    options = parser.parse_args()
    try:
        asyncio.run(run(options))
    except Exception:
        print(json.dumps({'ok': False, 'error': 'inventory_failed', 'message': 'Check profile/runtime availability. Raw response omitted to avoid disclosing private data.'}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
