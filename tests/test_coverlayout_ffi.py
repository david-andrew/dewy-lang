"""Independent C ABI coverage for varied record shapes and owned C pointers."""
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401


FIXTURES = Path(__file__).parent / 'fixtures/coverlayout_ffi'
EXPECTED = {
    'small_value': '3 42\n',
    'pair_value': '3.0 6.0\n',
    'nested_value': '2 41 1.5 4.0\n',
    'large_value': '2 4 6 8\n',
    'small_pointer': '2 40\n',
    'array_of_records': '42\n',
    'array_empty': '0\n',
    'allocated_pointer': '42\n',
    'fixed_field': '21 22\n',
    'mixed_registers': '42 3.0\n',
    'float_triple': '2.0 4.0 6.0\n',
    'stack_argument': '42\n',
}


@pytest.fixture(scope='module')
def library(tmp_path_factory):
    if platform.system() != 'Linux' or not shutil.which('cc'):
        pytest.skip('C ABI coverage requires Linux and cc')
    target = tmp_path_factory.mktemp('coverlayout-ffi') / 'librecords.so'
    result = subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC', FIXTURES / 'records.c', '-o', target],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return target


@pytest.mark.parametrize('name', EXPECTED)
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_c_abi_records(compiler, library, tmp_path, name, release):
    source = tmp_path / f'{name}.dewy'
    source.write_text('$runtime_checks\n\n'
                      + (FIXTURES / f'{name}.dewy.in').read_text().replace('LIBRARY', f"'{library}'"))
    binary = tmp_path / name
    flags = ['--release'] if release else []
    env = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10)
    assert (ran.returncode, ran.stdout) == (0, EXPECTED[name]), ran.stderr
