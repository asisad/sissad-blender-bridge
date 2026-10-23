import math
import pytest
from types import SimpleNamespace
import sissad_blender_bridge.windows_mouse as mouse_module
from sissad_blender_bridge.windows_mouse import gesture_points


def test_source_movement_precedes_crossing_and_release_target():
    path=gesture_points((100,500),(120,480),(700,200))
    assert path[0]==(100,500) and path[1]==(120,480) and path[-1]==(700,200)
    assert len(path)==14
    assert all(path[i][1]>=path[i+1][1] for i in range(len(path)-1))


@pytest.mark.parametrize('source,via,target',[
    ((0,0),(1,1),(100,100)),((math.nan,0),(20,0),(100,100)),
    ((0,0),(math.inf,0),(100,100)),((-1,0),(20,0),(100,100)),
    ((True,0),(20,0),(100,100)),
])
def test_invalid_input_cannot_build_a_gesture(source,via,target):
    with pytest.raises(ValueError):gesture_points(source,via,target)


@pytest.mark.parametrize('fail_at,expected_flags',[(1,[]),(16,[0xE001,2,4])])
def test_focus_or_coverage_failure_never_leaves_button_held(monkeypatch,fail_at,expected_flags):
    mouse=object.__new__(mouse_module.BlenderMouse)
    mouse.pid,mouse.hwnd=123,1
    mouse.u=SimpleNamespace(SetForegroundWindow=lambda _:True,GetAsyncKeyState=lambda _:0)
    mouse.screen_point=lambda point,size:point
    calls=[]
    def guard(point):
        calls.append(point)
        if len(calls)==fail_at:raise RuntimeError('Focus changed')
    mouse.guard=guard
    flags=[]
    mouse.send=lambda flag,point=None:flags.append(flag)
    monkeypatch.setattr(mouse_module.time,'sleep',lambda _:None)
    with pytest.raises(RuntimeError,match='Focus changed'):
        mouse.drag((100,500),(120,480),(700,200),(1440,852),execute=True)
    assert flags==expected_flags


def test_moved_window_rejected_before_pointer_or_input():
    mouse=object.__new__(mouse_module.BlenderMouse)
    mouse.initial_geometry=(0,0,100,100,0,0,100,90,0,-10)
    mouse.geometry=lambda:(10,0,110,100,0,0,100,90,-10,-10)
    # No user32 object is needed: changed geometry must stop first.
    with pytest.raises(RuntimeError,match='moved or resized'):
        mouse.guard((50,50))
