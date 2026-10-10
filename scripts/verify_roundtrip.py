"""Verify actual proxy transport, UI resources, polling roundtrip and saved files."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sissad_blender_bridge.client import serialize_result
from acceptance_live import extract

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / '.runtime/evidence'


def simple_snapshot():
    return """import bpy
import json
assert bpy.context.scene.get('sissad_bridge_test_session') is True
obj = bpy.data.objects['AI_Connection_Test']
result = {'acceptance_marker':'sissad-live-v1', 'version':bpy.app.version_string,
          'signal':bpy.context.scene.get('sissad_signal',0),
          'vertices':[list(v.co) for v in obj.data.vertices],
          'matrix':[list(row) for row in obj.matrix_world]}
print('SISSAD_ACCEPTANCE_JSON='+json.dumps(result))
"""


async def proxy_probe(profile, report):
    params = StdioServerParameters(command=str(ROOT / '.venv/Scripts/sissad-blender.exe'),
        args=['--config',str(ROOT/'config.local.json'),'serve','--profile',profile], env=dict(os.environ))
    with open(os.devnull, 'w') as err:
        async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                entry = {'profile':profile, 'server':init.serverInfo.model_dump(), 'tools':len(tools.tools)}
                result = await session.call_tool('execute_blender_code', {'code':simple_snapshot()})
                before = extract(result.model_dump(mode='json'))
                assert before, 'No scene evidence through proxy'
                entry['scene_version'] = before['version']
                if profile == 'lab52':
                    code = """import bpy
assert bpy.context.scene.get('sissad_bridge_test_session') is True
bpy.context.scene['sissad_signal']=0
def sissad_originated_change():
    bpy.context.scene['sissad_signal']=1
    return None
bpy.app.timers.register(sissad_originated_change, first_interval=1.0)
result={'scheduled':True}
"""
                    scheduled = await session.call_tool('execute_blender_code', {'code':code})
                    assert not scheduled.isError
                    await asyncio.sleep(2)
                    result = await session.call_tool('execute_blender_code', {'code':simple_snapshot()})
                    after = extract(result.model_dump(mode='json'))
                    assert after['signal'] == 1
                    assert before['vertices'] == after['vertices'] and before['matrix'] == after['matrix']
                    entry['blender_timer_to_client_poll'] = True
                if profile == 'community52':
                    resources = await session.list_resources()
                    entry['resources'] = [str(r.uri) for r in resources.resources]
                    ui = next(r for r in resources.resources if 'viewport' in str(r.uri))
                    contents = await session.read_resource(ui.uri)
                    assert contents.contents and any('html' in (c.mimeType or '') for c in contents.contents)
                    entry['viewport_ui_resource_read'] = True
                    screenshot_tool = next(t for t in tools.tools if t.name == 'look')
                    screenshot = await session.call_tool(screenshot_tool.name, {'mode':'camera','max_size':800})
                    assert not screenshot.isError
                    saved = serialize_result(screenshot, EVIDENCE)
                    assert any(c.get('saved') for c in saved['content']), 'No real screenshot returned'
                    entry['viewport_screenshot'] = saved
                report['probes'].append(entry)
                return before


async def main():
    report = {'passed':False, 'probes':[], 'reopened':[], 'limitations':['Polling of Blender-origin change, not push event streaming.', 'MCP UI resource delivery is not proof of UI rendering inside Codex.']}
    try:
        first = await proxy_probe('lab52',report)
        second = await proxy_probe('lab52',report)
        assert first['vertices'] == second['vertices'] and first['matrix'] == second['matrix']
        report['upstream_restart_preserved_scene'] = True
        await proxy_probe('community52',report)
        config = json.loads((ROOT/'config.local.json').read_text(encoding='utf-8-sig'))
        for profile in ('lab52','community52','lab53','community53'):
            executable = config['profiles']['lab'+profile[-2:]]['env']['BLENDER_PATH']
            result = await asyncio.to_thread(subprocess.run, [executable,'--background','--factory-startup','--offline-mode','--disable-autoexec',str(EVIDENCE/f'{profile}-acceptance.blend'),'--python-exit-code','1','--python',str(ROOT/'scripts/reopen_check.py')],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            assert result.returncode == 0, 'Independent reopen failed for '+profile
            row = next(line for line in result.stdout.splitlines() if line.startswith('SISSAD_REOPEN='))
            report['reopened'].append({'profile':profile,**json.loads(row.split('=',1)[1])})
            print(profile+': independent reopen passed',flush=True)
        report['passed']=True
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        (EVIDENCE/'roundtrip-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
    (EVIDENCE/'roundtrip.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    sys.exit(asyncio.run(main()))
