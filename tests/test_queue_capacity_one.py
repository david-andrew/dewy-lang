"""Contended ring generations stay distinct at every small capacity."""
import os
from pathlib import Path
import subprocess

import pytest
from tests.support import compiler  # noqa: F401
from tools.cores import on_cores


@pytest.mark.parametrize('release', [False, True])
def test_small_mpmc_generations(compiler, tmp_path, release):
    source = Path(__file__).parent / 'cases/queue_correctness/mpmc_contended.dewy'
    binary = tmp_path / 'contended'
    env = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           env=env, capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    for _ in range(20):
        ran = subprocess.run(on_cores([binary], 2), env=env, capture_output=True, text=True, timeout=5)
        assert (ran.returncode, ran.stdout) == (0, 'true\ntrue\ntrue\n'), ran.stderr
