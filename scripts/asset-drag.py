"""Arm/read/clean up the bounded review helper through the existing local Lab MCP."""
import argparse
import asyncio
import json
from pathlib import Path

from sissad_blender_bridge.client import BridgeClient
from sissad_blender_bridge import asset_drag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('config.local.json'))
    parser.add_argument('--profile', choices=('lab52', 'lab53'), default='lab52')
    sub = parser.add_subparsers(dest='action', required=True)
    arm = sub.add_parser('arm')
    arm.add_argument('--scene', required=True)
    arm.add_argument('--asset', choices=sorted(asset_drag.REVIEW_ASSETS), required=True)
    arm.add_argument('--library', type=Path, required=True)
    arm.add_argument('--root', type=Path, required=True)
    arm.add_argument('--sha256', required=True)
    arm.add_argument('--timeout', type=int, default=60)
    sub.add_parser('status')
    sub.add_parser('cleanup')
    options = parser.parse_args()
    # Fixed owned module only: never load a caller-supplied Python file.
    code = "import sys,importlib.util\nkey='sissad_review_asset_drag'\n"
    code += "m=sys.modules.get(key)\n"
    if options.action == 'arm':
        path = asset_drag.verified_library(options.library, options.root, options.sha256)
        module = str(Path(asset_drag.__file__).resolve())
        code += (f"if m is None:\n spec=importlib.util.spec_from_file_location(key,{module!r})\n"
                 " m=importlib.util.module_from_spec(spec)\n sys.modules[key]=m\n spec.loader.exec_module(m)\n")
        arguments = dict(library_file=str(path), library_root=str(options.root.resolve()),
                         library_hash=options.sha256, asset_name=options.asset,
                         scene_name=options.scene, allowed_assets=sorted(asset_drag.REVIEW_ASSETS),
                         timeout=options.timeout)
        code += f"result=m.arm(**{arguments!r})\n"
    elif options.action == 'status':
        code += "result=m.status() if m else {'status':'not_loaded'}\n"
    else:
        code += "if m: m.cleanup()\nresult={'status':'cleaned' if m else 'not_loaded'}\n"
    response = asyncio.run(BridgeClient(options.config).call_tool(
        options.profile, 'execute_blender_code', {'code': code}))
    print(json.dumps(response, ensure_ascii=True))
    body = response.get('structuredContent', {})
    if not body:
        try:
            body = json.loads(next(x['text'] for x in response.get('content', []) if x['type'] == 'text'))
        except (StopIteration, ValueError, KeyError):
            return 1
    if response.get('isError') or body.get('status') != 'ok':
        return 1
    state = body.get('result', {}).get('status')
    if options.action == 'arm':
        return 0 if state == 'armed' else 1
    if options.action == 'cleanup':
        return 0 if state in {'cleaned', 'not_loaded'} else 1
    return 1 if state == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
