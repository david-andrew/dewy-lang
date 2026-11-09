"""DEWY_SOFTWARE=1 on Windows draws with the software renderer and, with no display to show a
window on (here Wine with DISPLAY empty), opens none: the frames are drawn and the program exits,
as on Linux."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_cross_target_runs import build, run

GAME = """update = (dt:float64):>void => {}
draw = ():>void => {
    clear(rgb(0.0 0.0 0.0))
}
"""


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_software_renderer_opens_no_window_without_a_display(compiler, tmp_path, release):  # noqa: F811
    binary = build(compiler, tmp_path, GAME, 'x86_64-windows', *(['--release'] if release else []))
    status, out, err = run('x86_64-windows', binary,
                           setup='DISPLAY= WAYLAND_DISPLAY= WINEDEBUG=-all DEWY_NO_AUDIO=1 DEWY_SOFTWARE=1 DEWY_FRAMES=3')
    assert status == 0, out + err
    assert 'cannot open a window' not in err, err
