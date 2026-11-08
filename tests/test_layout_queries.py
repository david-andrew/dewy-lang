"""`size_of<T>` and `align_of<T>` against C's sizeof and alignof for the same records."""
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/layout_queries'


@pytest.mark.parametrize('mode', ['default', 'release'])
def test_layout_queries_match_c(compiler, tmp_path, mode):
    if platform.system() != 'Linux' or shutil.which('cc') is None:
        pytest.skip('the C comparison needs Linux and a C compiler')
    c_binary = tmp_path / 'records_c'
    built = subprocess.run(['cc', '-std=c11', FIXTURES / 'records.c', '-o', c_binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    expected = subprocess.run([c_binary], capture_output=True, text=True, timeout=10, check=True).stdout
    binary = tmp_path / 'records'
    flags = ['--release'] if mode == 'release' else []
    built = subprocess.run([compiler, 'build', FIXTURES / 'records.dewy', *flags, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, expected), ran.stderr
