"""Default array kernels use guarded vectors and retain checked debug loops."""
import platform
import re
import subprocess

import pytest

from tests.support import compiler
from tools.compiler.bench import CHECKSUMS_1000, prepare_source


@pytest.mark.core_quick
@pytest.mark.parametrize('debug', [False, True])
def test_default_shifted_array_vectors(compiler, tmp_path, debug):
    source = prepare_source('shifted_arrays', tmp_path)
    # The vectorization fixture explicitly requests modular reduction. The
    # benchmark retains exact arithmetic and measures its required checks.
    text = source.read_text().replace('array<int64>', "array<int64<overflow='wrap'>>")
    source.write_text(text.replace('let total:int64=0', "let total:int64<overflow='wrap'>=0"))
    binary = tmp_path / 'shifted-arrays'
    built = subprocess.run([compiler, 'build', source, '--ir',
                            *(['-g'] if debug else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    kernel = next(body for body in re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
                  if body.startswith('f_kernel_'))
    if platform.machine().lower() in ('x86_64', 'amd64'):
        assert (' = vld ' in kernel) == (not debug), kernel
    ran = subprocess.run([binary, '1000'], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert int(ran.stdout.split()[0]) == CHECKSUMS_1000['shifted_arrays']
