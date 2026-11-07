"""`window` gives a `Window` handle, or a `WindowError` value when there is no display to open one on."""
import os
import platform
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

pytestmark = pytest.mark.skipif(platform.system() != 'Linux', reason='display variables name X11 and Wayland displays')

MATCH = """main = () => {
    match window("t" 320 200) {
        w:Window => printl"opened"
        e:WindowError => printl"no window: {e.message}"
    }
}
"""


def run(compiler, tmp_path, source, **extra):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DEWY_NO_AUDIO': '1', **extra}
    env.pop('DEWY_SOFTWARE', None) if 'DEWY_SOFTWARE' not in extra else None
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path,
                          env=env)


def test_no_display_is_a_value(compiler, tmp_path):
    ran = run(compiler, tmp_path, MATCH, DEWY_PLATFORM='x11')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.startswith('no window: '), ran.stdout


def test_headless_software_window_is_a_handle(compiler, tmp_path):
    # (the control: the software renderer draws with no display, so the window opens)
    ran = run(compiler, tmp_path, MATCH, DEWY_SOFTWARE='1')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'opened\n'


def test_or_throw_ends_main_with_the_error(compiler, tmp_path):
    source = 'main = () => {\n    window("t" 320 200) or_throw;\n    printl"opened"\n}\n'
    ran = run(compiler, tmp_path, source, DEWY_PLATFORM='x11')
    assert ran.returncode == 1
    assert ran.stdout == ''
    assert ran.stderr.startswith('error: WindowError: '), ran.stderr
    control = run(compiler, tmp_path, source, DEWY_SOFTWARE='1')
    assert control.returncode == 0, control.stderr
    assert control.stdout == 'opened\n'


def test_an_unhandled_window_is_a_compile_error(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'main = ():>void => {\n    window("t" 320 200)\n    printl"x"\n}\n')
    assert ran.returncode == 1
    assert 'WindowError | Window' in ran.stderr
