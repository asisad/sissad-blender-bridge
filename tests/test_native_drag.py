"""The complete native gesture must exclude concurrent bridge writers."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def test_snapshot_gesture_and_readback_share_one_lock(monkeypatch, tmp_path):
    path=Path(__file__).resolve().parents[1]/'scripts'/'native-drag.py'
    spec=importlib.util.spec_from_file_location('native_drag_test',path)
    cli=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    state={'locked':False,'reads':0,'dragged':False}
    @contextmanager
    def lock(path):
        assert not state['locked'], 'The OS lock must never be acquired recursively'
        state['locked']=True
        try:yield
        finally:state['locked']=False
    class Client:
        lock_path=tmp_path/'shared.lock'
        async def _request(self,profile,method,**kwargs):
            assert state['locked'] and kwargs['arguments']['code']==cli.PROBE
            state['reads']+=1
            snapshot={'pid':123,'scene':'Review','marked_test':True,'simulation':False,
                      'helper_loaded':False,'modal':[],'mode':'OBJECT',
                      'regions':[{'area':'FILE_BROWSER','rect':[0,400,300,300]},
                                 {'area':'VIEW_3D','rect':[300,0,700,400]}],
                      'operators':['OBJECT_OT_collection_external_asset_drop'],
                      'objects':([{'name':'New','matrix':[],'collection':'Asset','meshes':1,'vertices':8}]
                                 if state['dragged'] else [])}
            return SimpleNamespace(model_dump=lambda **_: {
                'structuredContent':{'status':'ok','result':snapshot}})
    class Mouse:
        def __init__(self,*_):assert state['locked']
        def screen_point(self,point,size):return point
        def blender_point(self,point):return point
        def drag(self,*args,**kwargs):
            assert state['locked'] and state['reads']==1
            state['dragged']=True
            return {}
        def close(self):assert state['locked']
    monkeypatch.setattr(cli,'writer_lock',lock)
    monkeypatch.setattr(cli,'BridgeClient',lambda _:Client())
    monkeypatch.setattr(cli,'BlenderMouse',Mouse)
    monkeypatch.setattr(cli.time,'sleep',lambda _:None)
    evidence=tmp_path/'proof.json'
    monkeypatch.setattr(sys,'argv',['native-drag','--exe','blender.exe','--scene','Review',
        '--asset','Asset','--source','100,500','--via','120,480','--target','700,200',
        '--screenshot-size','1000,700','--execute','--evidence',str(evidence)])
    assert cli.main()==0
    assert state['reads']==2 and not state['locked']
    assert json.loads(evidence.read_text())['passed'] is True
