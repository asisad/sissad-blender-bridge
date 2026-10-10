"""Blender GUI bootstrap: owned disposable scene, both installed upstreams.

Use only with a newly launched process, never a user's already-open scene.
"""
import argparse
import json
import sys
from pathlib import Path

import addon_utils
import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--lab-port', type=int, required=True)
    parser.add_argument('--community-port', type=int, required=True)
    parser.add_argument('--test-scene', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    for name in ('blender_mcp_addon', 'blender_mcp'):
        addon_utils.enable(name, default_set=True)
    prefs = bpy.context.preferences.addons['blender_mcp_addon'].preferences
    prefs.host, prefs.port = '127.0.0.1', args.lab_port
    bpy.context.scene.blendermcp_port = args.community_port
    if args.test_scene:
        bpy.context.scene['sissad_bridge_test_session'] = True
    # Establish the two local services explicitly; pending autostart is idempotent.
    from blender_mcp_addon import mcp_to_blender_server
    if not mcp_to_blender_server.is_running():
        bpy.ops.blmcp.server_start()
    import blender_mcp
    existing = getattr(bpy.types, 'blendermcp_server', None)
    if existing is None:
        existing = blender_mcp.BlenderMCPServer(host='127.0.0.1', port=args.community_port)
        bpy.types.blendermcp_server = existing
    elif existing.port != args.community_port or existing.host not in ('127.0.0.1', 'localhost'):
        raise RuntimeError('Existing community server targets a different address')
    existing.start()
    if not existing.running or not mcp_to_blender_server.is_running():
        raise RuntimeError('One or both upstream servers failed to start')
    bpy.context.scene.blendermcp_server_running = True
    root = Path(args.root)
    data = {'version': bpy.app.version_string, 'lab_port': args.lab_port,
            'community_port': args.community_port, 'background': bpy.app.background}
    (root / '.runtime/evidence' / ('ready-' + str(bpy.app.version[1]) + '.json')).write_text(json.dumps(data), encoding='utf-8')


main()
