"""Ordinary programs (tests/cases/arm64_programs) built for aarch64-linux, in default and release
builds, under qemu-aarch64: each prints what its golden output (x86-64's) says."""
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

CASES = sorted((Path(__file__).parent / 'cases/arm64_programs').glob('*.dewy'))


def header_args(source: Path) -> list[str]:
    for line in source.read_text().splitlines():
        if not line.startswith('#'):
            break
        if line.startswith('# args:'):
            return shlex.split(line.partition(':')[2])
    return []


@pytest.mark.parametrize('flags', [(), ('--release',)], ids=['default', 'release'])
@pytest.mark.parametrize('source', CASES, ids=[case.stem for case in CASES])
def test_arm64_program(compiler, tmp_path, source, flags):
    if (runner := shutil.which('qemu-aarch64')) is None:
        pytest.skip('no qemu-aarch64')
    binary = tmp_path / source.stem
    built = subprocess.run([compiler, 'build', source, '--target', 'aarch64-linux', *flags, '-o', binary],
                           capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([runner, binary, *header_args(source)], capture_output=True, text=True,
                         timeout=300, cwd=tmp_path, env={'PATH': '/usr/bin:/bin', 'DEWY_NO_AUDIO': '1'})
    assert (ran.returncode, ran.stdout) == (0, source.with_suffix('.out').read_text()), ran.stderr[-2000:]
