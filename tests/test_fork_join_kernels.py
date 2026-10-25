"""Stage-one kernel outputs agree with their sequential and OpenMP readings."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.support import compiler

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('forkjoin_bench', ROOT / 'bench/parallel/run.py')
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


@pytest.mark.parametrize('kernel', BENCH.SMALL)
def test_kernel_checksum(compiler, tmp_path, kernel):
    cc = shutil.which('gcc')
    if not cc:
        pytest.skip('GCC/OpenMP unavailable')
    source = ROOT / 'bench/parallel' / kernel
    dewy, c = tmp_path / 'dewy', tmp_path / 'c'
    built = subprocess.run([cc, '-O3', '-fopenmp', source.with_suffix('.c'), '-lm', '-o', c],
                           capture_output=True, text=True, timeout=30)
    if built.returncode and ('omp.h' in built.stderr or 'cannot find -lgomp' in built.stderr):
        pytest.skip('GCC OpenMP development files unavailable')
    assert built.returncode == 0, built.stderr
    built = subprocess.run([compiler, 'build', source.with_suffix('.dewy'), '--release', '-o', dewy],
                           capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stderr
    expected = None
    for threads, serial in ((1, True), (1, False), (2, False), (4, False)):
        env = dict(os.environ, DEWY_THREADS=str(threads), OMP_NUM_THREADS=str(threads))
        for binary in (c, dewy):
            result = subprocess.run([binary, str(BENCH.SMALL[kernel]), *(['serial'] if serial else [])],
                                    env=env, capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stderr
            value, ns = map(int, result.stdout.split())
            assert ns >= 0
            if expected is None:
                expected = value
            assert value == expected
