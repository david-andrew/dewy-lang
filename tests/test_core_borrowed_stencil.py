"""Flat stencil offsets retain scalar meaning and checked borrowed buffers."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_borrowed_stencil_odd_sizes(compiler, tmp_path, release):
    output = tmp_path / 'jacobi'
    build = subprocess.run([compiler, 'build', ROOT / 'bench/parallel/jacobi.dewy',
                            '-o', output, *(['--release'] if release else [])],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    for n in (1, 2, 3, 9, 31):
        a = [[float((i+j) % 17) for j in range(n)] for i in range(n)]
        for _ in range(20):
            b = [row[:] for row in a]
            for i in range(1, n-1):
                for j in range(1, n-1):
                    b[i][j] = (a[i-1][j]+a[i+1][j]+a[i][j-1]+a[i][j+1])*0.25
            a = b
        expected = sum(int(x*1024) for row in a for x in row)
        for tail in ([], ['serial']):
            run = subprocess.run([output, str(n), *tail], capture_output=True, text=True,
                                 env=dict(os.environ, SLOPPY_THREADS='2'), timeout=30)
            assert run.returncode == 0, run.stderr
            assert int(run.stdout.split()[0]) == expected
