"""ui_begin finishes a menu left open, with a warning in debug builds only."""
import os
import subprocess
import sys

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''menu=():>void=>{
    ui_begin("first" vec2(0 0))
    ui_begin("second" vec2(0 0))
    ui_end()
    ui_begin("first" vec2(0 0))
    ui_begin("second" vec2(0 0))
    ui_end()
}
main=()=>{
    menu()
    printl("ok")
}
$runtime_checks
'''

WARNING = "warning: the menu 'first' has no `ui_end()` before the next ui_begin; finished it there\n"


@pytest.mark.skipif(sys.platform != 'linux', reason='headless build')
@pytest.mark.parametrize(('flags', 'stderr'), [([], WARNING), (['--release'], '')], ids=['debug', 'release'])
def test_open_menu_finished_with_debug_warning(compiler, tmp_path, flags, stderr):
    path = tmp_path / 'main.dewy'
    path.write_text(SOURCE)
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    environment = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DEWY_NO_AUDIO': '1'}
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, env=environment)
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, 'ok\n', stderr)
