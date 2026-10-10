"""Bounded read-only polling, not push/event/video streaming."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import sys

from sissad_blender_bridge import BridgeClient

CODE = '''import bpy
import json
scene = bpy.context.scene
objects = []
for obj in sorted(scene.objects, key=lambda item: item.name):
    try:
        selected = obj.select_get()
    except RuntimeError:
        selected = False
    objects.append({'name': obj.name, 'type': obj.type, 'location': list(obj.location),
                    'rotation_mode': obj.rotation_mode, 'rotation_euler': list(obj.rotation_euler),
                    'rotation_quaternion': list(obj.rotation_quaternion),
                    'rotation_axis_angle': list(obj.rotation_axis_angle),
                    'scale': list(obj.scale), 'selected': selected})
result = {'watch_marker': 'sissad-watch-v1', 'objects': objects,
          'frame': scene.frame_current, 'subframe': scene.frame_subframe}
print('SISSAD_WATCH_JSON=' + json.dumps(result))
'''


def extract(payload):
    if isinstance(payload, dict):
        if payload.get('watch_marker') == 'sissad-watch-v1':
            return payload
        values = payload.values()
    elif isinstance(payload, list):
        values = payload
    elif isinstance(payload, str):
        for line in payload.splitlines():
            if line.startswith('SISSAD_WATCH_JSON='):
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
    previous = None
    async with client.persistent(options.profile) as session:
        for sample in range(options.count):
            response = await session.call_tool(options.profile, 'execute_blender_code', {'code': CODE})
            result = None if response.get('isError') else extract(response)
            if result is None:
                raise RuntimeError('Polling response did not contain a successful snapshot.')
            fingerprint = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if fingerprint != previous:
                print(json.dumps({'mode': 'polling', 'profile': options.profile, 'sample': sample,
                                  'observed_utc': datetime.now(timezone.utc).isoformat(),
                                  'fingerprint': fingerprint, 'snapshot': result}, ensure_ascii=True), flush=True)
                previous = fingerprint
            if sample + 1 < options.count:
                await asyncio.sleep(options.interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.local.json')
    parser.add_argument('--profile', default='lab52')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--count', type=int, default=30, help='Number of samples, from 1 through 10000')
    options = parser.parse_args()
    if not math.isfinite(options.interval) or options.interval < 0.25:
        parser.error('--interval must be finite and at least 0.25 seconds')
    if not 1 <= options.count <= 10000:
        parser.error('--count must be between 1 and 10000')
    try:
        asyncio.run(run(options))
    except KeyboardInterrupt:
        return 130
    except Exception:
        print(json.dumps({'ok': False, 'error': 'polling_failed', 'message': 'Read-only polling stopped; no automatic retry was attempted.'}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
