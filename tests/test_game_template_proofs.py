"""Templates and small regressions exercise proofs outside the library directory."""
import os
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', ['game', 'story'])
def test_game_template_without_optins(compiler, tmp_path, name):
    source = (ROOT / 'lib/new/dewy' / (name + '.dewy')).read_text()
    assert '$runtime_checks' not in source and '$prototype' not in source
    path = tmp_path / (name + '.dewy')
    path.write_text(source)
    checked = subprocess.run([compiler, 'check', '--obligations', path], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert not checked.stdout.strip(), checked.stdout
    env = {**os.environ, 'DEWY_SOFTWARE': '1', 'DEWY_FRAMES': '2', 'DEWY_SCREENSHOT': str(tmp_path / 'frame.png'), 'DISPLAY': '', 'WAYLAND_DISPLAY': ''}
    ran = subprocess.run([compiler, 'run', path], capture_output=True, text=True, env=env, timeout=90)
    assert ran.returncode == 0, ran.stdout + ran.stderr
