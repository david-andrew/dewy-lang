"""A small checked stencil remains vectorizable inside a large function."""
import os
import platform
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_large_jacobi_function_vectorizes(compiler, tmp_path, release):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('native loop vectors require x86-64')
    binary = tmp_path / 'jacobi'
    built = subprocess.run(
        [compiler, 'build', ROOT / 'bench/parallel/jacobi.dewy', '--ir',
         '-o', binary, *(['--release'] if release else [])],
        capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    # The recursive partition helper contains extensive shape and exact-index
    # guards around its small stencil. Census/copy vectors elsewhere do not
    # establish that the floating-point stencil itself was vectorized.
    bodies = re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
    stencils = [body for body in bodies if ' = fadd ' in body]
    assert stencils
    for body in stencils:
        assert re.search(r' = vbin .*c=0 imm=1 ', body), body
    for n in (3, 9, 33, 65):
        a = [[float((i + j) % 17) for j in range(n)] for i in range(n)]
        for _ in range(20):
            b = [row[:] for row in a]
            for i in range(1, n - 1):
                for j in range(1, n - 1):
                    b[i][j] = (a[i-1][j] + a[i+1][j] + a[i][j-1] + a[i][j+1]) * 0.25
            a = b
        expected = sum(int(value * 1024) for row in a for value in row)
        for no_avx in (False, True):
            env = {k: v for k, v in os.environ.items() if k != 'DEWY_NO_AVX'}
            if no_avx:
                env['DEWY_NO_AVX'] = '1'
            ran = subprocess.run([binary, str(n), 'serial'], env=env,
                                 capture_output=True, text=True, timeout=30)
            assert ran.returncode == 0, ran.stderr
            assert int(ran.stdout.split()[0]) == expected
