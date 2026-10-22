import hashlib

import pytest

from sissad_blender_bridge.asset_drag import Gesture, verified_library


def test_release_requires_press_crossing_and_only_commits_once():
    g = Gesture()
    assert g.event('LEFTMOUSE', 'RELEASE', False, True, (100, 100)) == 'PASS'
    assert g.event('LEFTMOUSE', 'PRESS', True, False, (0, 0)) == 'CONSUME'
    assert g.event('MOUSEMOVE', 'NOTHING', False, True, (100, 100)) == 'CONSUME'
    assert g.event('LEFTMOUSE', 'RELEASE', False, True, (100, 100)) == 'COMMIT'
    assert g.event('LEFTMOUSE', 'RELEASE', False, True, (100, 100)) == 'IGNORE'


def test_press_outside_source_and_repeated_press_cancel():
    g = Gesture()
    assert g.event('LEFTMOUSE', 'PRESS', False, False, (0, 0)) == 'CANCEL'
    assert g.event('LEFTMOUSE', 'RELEASE', False, True, (100, 100)) == 'IGNORE'
    g = Gesture()
    g.event('LEFTMOUSE', 'PRESS', True, False, (0, 0))
    assert g.event('LEFTMOUSE', 'PRESS', True, False, (1, 1)) == 'CANCEL'


@pytest.mark.parametrize('kind,value,source,target,pos', [
    ('ESC', 'PRESS', False, False, (0, 0)),
    ('RIGHTMOUSE', 'PRESS', False, False, (0, 0)),
    ('LEFTMOUSE', 'RELEASE', False, False, (100, 100)),
    ('LEFTMOUSE', 'RELEASE', True, True, (1, 1)),
])
def test_cancelled_or_invalid_drop_never_commits(kind, value, source, target, pos):
    g = Gesture()
    g.event('LEFTMOUSE', 'PRESS', True, False, (0, 0))
    assert g.event(kind, value, source, target, pos) == 'CANCEL'


def test_library_rejects_escape_changed_content_and_wrong_type(tmp_path):
    root = tmp_path / 'assets'
    root.mkdir()
    inside = root / 'approved.blend'
    outside = tmp_path / 'other.blend'
    inside.write_bytes(b'approved')
    outside.write_bytes(b'approved')
    digest = hashlib.sha256(b'approved').hexdigest()
    assert verified_library(inside, root, digest) == inside
    with pytest.raises(ValueError):
        verified_library(outside, root, digest)
    inside.write_bytes(b'changed')
    with pytest.raises(ValueError):
        verified_library(inside, root, digest)
