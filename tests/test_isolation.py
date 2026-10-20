"""Ambient isolation must never depend on a source pathname."""
from pathlib import Path
import subprocess

import pytest

from tests.test_core import compiler


FIXTURES = Path(__file__).parent / 'fixtures/isolation'


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('name', ['pathname', 'snapshot'])
def test_isolation_pathname(compiler, tmp_path, release, name):
    results = []
    for directory in ('ordinary', 'lib/core'):
        location = tmp_path / directory
        location.mkdir(parents=True)
        source = location / f'{name}.jo'
        source.write_text((FIXTURES / source.name).read_text())
        program = location / 'program'
        built = subprocess.run(
            [compiler, 'build', source, '-o', program,
             *(['--release'] if release else [])],
            capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([program], capture_output=True, text=True, timeout=10)
        results.append((ran.returncode, ran.stdout))
        if name == 'pathname':
            assert ran.returncode == 101, ran.stdout + ran.stderr
            assert 'index 2' in ran.stdout + ran.stderr
        else:
            assert ran.returncode == 0, ran.stderr
            assert ran.stdout == '[11, 21, 31]\n[10, 20, 30]\n'
    assert results[0] == results[1]
