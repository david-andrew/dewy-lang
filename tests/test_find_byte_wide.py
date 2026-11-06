"""Long byte searches take 32 bytes a step on AVX2, with the same answers without it."""
import os
import platform
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize('release', [False, True])
def test_wide_and_plain_paths_agree(compiler, tmp_path, release):  # noqa: F811
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('AVX2 is x86-64 only')
    source = os.path.join(ROOT, 'tests/cases/optimizer/find_byte_wide.dewy')
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    assert re.search(r' = findbyte .*imm=2 ', built.stdout)
    for extra in ({}, {'DEWY_NO_AVX': '1'}):
        env = {k: v for k, v in os.environ.items() if k != 'DEWY_NO_AVX'} | extra
        ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=120)
        assert (ran.returncode, ran.stdout) == (0, '44850 0\n'), ran.stderr
