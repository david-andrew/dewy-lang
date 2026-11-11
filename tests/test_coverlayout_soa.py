"""Struct-of-arrays storage and mutation in the existing Jo surface."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401


FIXTURES = Path(__file__).parent / 'fixtures/coverlayout_soa'
PROGRAMS = sorted(FIXTURES.glob('*.jo'))


@pytest.mark.parametrize('source', PROGRAMS, ids=lambda p: p.stem)
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_soa_layout(compiler, tmp_path, source, release):
    binary = tmp_path / source.stem
    flags = ['--release'] if release else []
    env = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10)
    expected = source.with_suffix('.out').read_text()
    assert (ran.returncode, ran.stdout) == (0, expected), ran.stderr
