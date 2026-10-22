"""Dewy's `$extern`, `$export` and `ptr<T>` against an independently compiled C library."""
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/dewy_ffi'


@pytest.fixture(scope='module')
def harness(tmp_path_factory):
    if platform.system() != 'Linux' or shutil.which('cc') is None:
        pytest.skip('C interoperability checks require Linux and a C compiler')
    library = tmp_path_factory.mktemp('dewy-ffi') / 'libharness.so'
    built = subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC', FIXTURES / 'harness.c', '-o', library],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    return library


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['default', 'release'])
def test_dewy_ffi_harness(compiler, tmp_path, harness, mode):
    source = tmp_path / 'harness.dewy'
    source.write_text((FIXTURES / 'harness.dewy.in').read_text().replace('LIBRARY', f"'{harness}'"))
    binary = tmp_path / 'harness'
    flags = ['--release'] if mode == 'release' else []
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary], capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, (ran.returncode, ran.stdout, ran.stderr)
    assert ran.stdout == '42\n1234\n12 104 67\n[1 2 30 4]\ntrue\n[6.0 8.0]\n1 0\n'
