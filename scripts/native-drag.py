"""Approved local mouse gesture; actual native Blender drop independently verified."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import time

from sissad_blender_bridge.client import BridgeClient, writer_lock, serialize_result
from sissad_blender_bridge.windows_mouse import BlenderMouse

PROBE = '''import bpy,os,sys
s=bpy.context.scene
result={'pid':os.getpid(),'scene':s.name,'marked_test':bool(s.get('sissad_bridge_test_session')),
'simulation':bpy.app.use_event_simulate,'mode':bpy.context.mode,'file':bpy.data.filepath,
'helper_loaded':'sissad_review_asset_drag' in sys.modules,
'regions':[{ 'area':a.type,'rect':[r.x,r.y,r.width,r.height]} for a in bpy.context.screen.areas for r in a.regions if r.type=='WINDOW' and a.type in ['FILE_BROWSER','VIEW_3D']],
'modal':[o.bl_idname for o in bpy.context.window.modal_operators],
'operators':[o.bl_idname for o in list(bpy.context.window_manager.operators)[-10:]],
'objects':[{'name':o.name,'matrix':[list(r) for r in o.matrix_world],
'collection':o.instance_collection.name if o.instance_collection else None,
'meshes':sum(x.type=='MESH' for x in o.instance_collection.all_objects) if o.instance_collection else 0,
'vertices':sum(len(x.data.vertices) for x in o.instance_collection.all_objects if x.type=='MESH') if o.instance_collection else 0} for o in s.objects]}
'''


def read_snapshot(client, profile):
    # Caller holds the shared non-reentrant writer lock for the whole gesture.
    raw = serialize_result(asyncio.run(client._request(
        profile, 'call', tool='execute_blender_code', arguments={'code':PROBE}, timeout=30)), None)
    body = raw.get('structuredContent')
    if not body:
        body=json.loads(next(x['text'] for x in raw['content'] if x['type']=='text'))
    if raw.get('isError') or body.get('status')!='ok':
        raise RuntimeError('Blender snapshot failed; do not dispatch mouse input')
    return body['result']


def pair(text):
    result=tuple(float(x) for x in text.split(','))
    if len(result)!=2:raise argparse.ArgumentTypeError('Use x,y')
    return result


def region_contains(regions, area, point):
    return any(r['area']==area and r['rect'][0]<=point[0]<r['rect'][0]+r['rect'][2]
               and r['rect'][1]<=point[1]<r['rect'][1]+r['rect'][3] for r in regions)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('config.local.json'))
    p.add_argument('--profile',default='lab52')
    p.add_argument('--pid',type=int,help='Optional expected PID; otherwise read from the configured local Lab connection')
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--scene',required=True)
    p.add_argument('--asset',required=True)
    for name in ('source','via','target','screenshot-size'):p.add_argument('--'+name,type=pair,required=True)
    p.add_argument('--execute',action='store_true',help='Default is a dry run; explicit local-input authorization required')
    p.add_argument('--evidence',type=Path)
    o=p.parse_args()
    if o.evidence and o.evidence.exists():raise ValueError('Refusing to overwrite evidence')
    client=BridgeClient(o.config)
    with writer_lock(client.lock_path):
        before=read_snapshot(client,o.profile)
        if o.pid is None:o.pid=before['pid']
        if (before['pid']!=o.pid or before['scene']!=o.scene or not before['marked_test'] or
            before['simulation'] or before['helper_loaded'] or before['modal'] or before['mode']!='OBJECT'):
            raise RuntimeError('Expected the normal-input Blender process and marked review scene, without helpers/modals')
        mouse=BlenderMouse(o.pid,o.exe)
        try:
            for point,area in [(o.source,'FILE_BROWSER'),(o.via,'FILE_BROWSER'),(o.target,'VIEW_3D')]:
                native=mouse.blender_point(mouse.screen_point(point,o.screenshot_size))
                if not region_contains(before['regions'],area,native):
                    raise RuntimeError('Gesture must start and move inside Asset Browser, then end in the 3D WINDOW region')
            result=mouse.drag(o.source,o.via,o.target,o.screenshot_size,execute=o.execute)
        finally:mouse.close()
        result['before']=before
        if o.execute:
            time.sleep(.4)
            after=read_snapshot(client,o.profile)
            old={x['name']:x for x in before['objects']}
            new=[x for x in after['objects'] if x['name'] not in old]
            result.update(after=after,added=new,
                previous_unchanged=all(x['name'] not in old or x['matrix']==old[x['name']]['matrix'] for x in after['objects']))
            result['passed']=(after['scene']==before['scene'] and after['pid']==o.pid and
                not after['simulation'] and not after['helper_loaded'] and not after['modal'] and
                len(new)==1 and bool(new[0]['collection']) and
                bool(re.fullmatch(re.escape(o.asset)+r'(?:\.\d+)?',new[0]['collection'])) and
                new[0]['meshes']>0 and new[0]['vertices']>0 and result['previous_unchanged'] and
                len(after['objects'])==len(before['objects'])+1 and
                after['operators'][-1:] == ['OBJECT_OT_collection_external_asset_drop'])
        if o.evidence:
            with o.evidence.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps(result,ensure_ascii=True))
        return 0 if not o.execute or result['passed'] else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error),'retry':'Inspect Blender before retrying; no automatic replay.'}))
        raise SystemExit(1)
