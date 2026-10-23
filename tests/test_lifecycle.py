import pytest
from sissad_blender_bridge.lifecycle import lifecycle_action


@pytest.mark.parametrize('present,local,runtime,due,expected',[
    (False,False,False,True,'wait_blender'),
    (False,True,False,True,'wait_blender'),
    (False,True,True,False,'stop'),
    (True,False,False,True,'wait_local'),
    (True,False,True,True,'wait_local'),
    (True,True,True,False,'observe'),
    (True,True,False,False,'retry_wait'),
    (True,True,False,True,'connect'),
])
def test_presence_readiness_and_backoff_gate_tunnel(present,local,runtime,due,expected):
    assert lifecycle_action(blender_running=present,local_ready=local,
                            runtime_running=runtime,retry_due=due)==expected
