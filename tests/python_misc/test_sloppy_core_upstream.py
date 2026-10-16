"""Focused pinned-core regressions for changes to shared lowering/optimization."""
import os
import subprocess
from pathlib import Path

import pytest

from tools.sloppy_core.build import PIN

CASES = ('arrays', 'cow', 'bounds', 'loops', 'loopdecl', 'loopopt', 'optloops',
         'loop_combined_mut', 'loop_kv_mut', 'arg_alias_copy', 'loop_and_unpack')


@pytest.mark.parametrize('name', CASES)
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_pinned_core_loops(tmp_path, name, release):
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    reference = os.environ.get('DEWY_SLOPPY_ROOT')
    if not compiler or not reference:
        pytest.skip('set DEWY_CORE_COMPILER and DEWY_SLOPPY_ROOT for pinned upstream checks')
    compiler = Path(compiler).resolve(strict=True)
    reference = Path(reference).resolve(strict=True)
    source = tmp_path / f'{name}.jo'
    # Read committed fixtures, not the user's potentially modified checkout.
    def pinned(extension):
        return subprocess.check_output(['git', '-C', reference, 'show',
                                        f'{PIN}:tests/t/{name}.{extension}'])
    source.write_bytes(pinned('jo'))
    expected = pinned('out').decode()
    binary = tmp_path / name
    flags = ['--release'] if release else []
    env = {k: v for k, v in os.environ.items() if not k.startswith('SLOPPY_')}
    env.update(SLOPPY_LIB=str(compiler.parent.parent / 'lib'), SLOPPY_EMIT_WORKERS='1')
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == expected
