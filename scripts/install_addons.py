"""Run with Blender --background --python; install pinned upstream copies.

Only touches add-ons owned by this integration and their preference entries.
An external installer must back up userpref.blend before invoking this file.
"""
import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

import addon_utils
import bpy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--lab-port', type=int, required=True)
    parser.add_argument('--community-port', type=int, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    root = Path(args.root).resolve()
    target = Path(bpy.utils.user_resource('SCRIPTS', path='addons', create=True))
    backup = root / '.runtime' / 'backups' / (bpy.app.version_string.replace(' ', '_') + '-' + uuid.uuid4().hex)
    backup.mkdir(parents=True, exist_ok=True)
    for name in ('blender_mcp_addon', 'blender_mcp.py'):
        dest = target / name
        if dest.exists():
            saved = backup / name
            if saved.exists():
                raise RuntimeError('Existing backup; inspect before reinstall: ' + str(saved))
            if dest.is_dir():
                shutil.copytree(dest, saved)
            else:
                shutil.copy2(dest, saved)
    for module in ('blender_mcp_addon', 'blender_mcp'):
        if module in bpy.context.preferences.addons:
            addon_utils.disable(module, default_set=False)
        for loaded in list(sys.modules):
            if loaded == module or loaded.startswith(module + '.'):
                del sys.modules[loaded]
    lab_source = root / '.runtime/upstream/lab/addon/blender_mcp_addon'
    shutil.copytree(lab_source, target / 'blender_mcp_addon', dirs_exist_ok=True)
    community = (root / '.runtime/upstream/community/addon.py').read_text(encoding='utf-8')
    # Installation-specific defaults; original checkout remains untouched.
    community = community.replace("host='localhost', port=9876", "host='127.0.0.1', port=" + str(args.community_port))
    community = community.replace('default=9876', 'default=' + str(args.community_port))
    (target / 'blender_mcp.py').write_text(community, encoding='utf-8')
    bpy.utils.refresh_script_paths()
    addon_utils.modules_refresh()
    for module in ('blender_mcp_addon', 'blender_mcp'):
        addon_utils.enable(module, default_set=True, persistent=True)
        if module not in bpy.context.preferences.addons:
            raise RuntimeError('Could not enable ' + module)
    prefs = bpy.context.preferences.addons['blender_mcp_addon'].preferences
    prefs.host = '127.0.0.1'
    prefs.port = args.lab_port
    prefs.use_autostart = True
    bpy.context.scene.blendermcp_port = args.community_port
    # Online access is needed by Lab even for loopback; record this preference.
    bpy.context.preferences.system.use_online_access = True
    bpy.ops.wm.save_userpref()
    result = {'blender': bpy.app.version_string, 'addon_directory': str(target),
              'lab_port': args.lab_port, 'community_port': args.community_port,
              'addons': sorted(a.module for a in bpy.context.preferences.addons)}
    (root / '.runtime/evidence' / ('install-' + str(bpy.app.version[1]) + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


main()
