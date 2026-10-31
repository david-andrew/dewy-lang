"""No game or draw program run by a harness reaches the desktop (tools/headless.py).

The pytest session, the golden-case runner and the harness entry points give every
child an empty DISPLAY and WAYLAND_DISPLAY; tests/cases/game/headless_window.dewy is
the golden-case side of the same check."""
import os
import platform
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tools import cases, core, headless
from tools.compiler import bench, dewy_fuzz, dewy_fuzz_targeted, member_replay_diff, speed, truncation_fuzz

GAME = ('printl"DISPLAY=[{env("DISPLAY") ?? "unset"}] WAYLAND_DISPLAY=[{env("WAYLAND_DISPLAY") ?? "unset"}]"\n'
        'draw = () => { circle(vec2(100 100) 20 RED) }\n')
SEEN = 'DISPLAY=[] WAYLAND_DISPLAY=[]'
CASE = 'game/headless_window'


def test_pytest_children_see_no_display(compiler, tmp_path):
    assert os.environ.get('DISPLAY') == '' and os.environ.get('WAYLAND_DISPLAY') == ''
    assert os.environ.get('DEWY_NO_AUDIO') == '1'
    assert 'WAYLAND_SOCKET' not in os.environ
    source = tmp_path / 'game.dewy'
    source.write_text(GAME)
    # Inherits the session's environment; a few frames bound it should a window open after all.
    ran = subprocess.run([compiler, 'run', source], cwd=tmp_path, env={**os.environ, 'DEWY_FRAMES': '2'},
                         capture_output=True, text=True, timeout=120)
    assert ran.stdout.splitlines()[:1] == [SEEN], ran.stdout + ran.stderr
    if platform.system() == 'Linux':
        assert ran.returncode == 1 and 'cannot open a window' in ran.stderr, ran.stdout + ran.stderr



@pytest.mark.skipif(platform.system() != 'Linux', reason='display variables name X11 and Wayland displays')
def test_software_game_runs_headless_with_empty_display(compiler, tmp_path):
    # Empty display variables mean no display, as unset ones do: the software renderer
    # draws its frames without a window (no DEWY_SCREENSHOT needed).
    source = tmp_path / 'game.dewy'
    source.write_text(GAME)
    ran = subprocess.run([compiler, 'run', source], cwd=tmp_path, capture_output=True, text=True, timeout=120,
                         env={**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': '', 'DEWY_SOFTWARE': '1',
                              'DEWY_FRAMES': '3'})
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == [SEEN], ran.stdout + ran.stderr


def test_case_environment_hides_the_display(monkeypatch):
    monkeypatch.setenv('DISPLAY', ':99')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-none')
    monkeypatch.setenv('WAYLAND_SOCKET', '99')
    env = cases.clean_environment()
    assert env['DISPLAY'] == '' and env['WAYLAND_DISPLAY'] == '' and 'WAYLAND_SOCKET' not in env


@pytest.mark.skipif(platform.system() != 'Linux', reason='other hosts open windows without display variables')
def test_core_case_run_hides_the_display(compiler, monkeypatch):
    # A display in the caller's environment is emptied by tools.core itself, and the
    # golden game case sees none (its expected output says so).
    monkeypatch.setenv('DISPLAY', ':99')
    monkeypatch.setenv('WAYLAND_DISPLAY', 'wayland-none')
    assert core.main(['cases', '--compiler', str(compiler), '-k', CASE, '-n', '1']) == 0
    assert os.environ['DISPLAY'] == '' and os.environ['WAYLAND_DISPLAY'] == ''


@pytest.mark.parametrize('main', [
    lambda: bench.main(['--help'], ROOT), lambda: speed.main(['--help'], ROOT),
    lambda: dewy_fuzz.main(['--help']), lambda: dewy_fuzz_targeted.main(['--help']),
    lambda: truncation_fuzz.main(['--help']), lambda: member_replay_diff.main(['--help']),
], ids=['bench', 'speed', 'dewy_fuzz', 'dewy_fuzz_targeted', 'truncation_fuzz', 'member_replay_diff'])
def test_harness_entry_points_go_headless(main, monkeypatch):
    calls = []
    monkeypatch.setattr(headless, 'activate', lambda: calls.append(True))
    with pytest.raises(SystemExit):
        main()
    assert calls
