"""C function pointers validate every nested parameter, result and pointee."""
import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

DATA = Path(__file__).parent / 'fixtures/ffi_callback_signature'
REJECT = [
    ('callback_signature_int_reject', '`int`'),
    ('callback_signature_array_int32_reject', 'array<int32>'),
    ('callback_return_int_reject', '`int`'),
    ('callback_return_string_reject', 'string'),
    ('callback_return_array_uint8_reject', 'array<uint8>'),
    ('callback_return_ptr_array_uint8_reject', 'array<uint8>'),
    ('callback_return_ptr_int_reject', 'int'),
    ('callback_return_x_int32_reject', 'C boundary'),
    ('nested_result', '<():>int>'),
    ('nested_parameter', 'cannot cross the C boundary'),
]


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('name,diagnostic', REJECT)
def test_callback_signature_reject(compiler, tmp_path, release, name, diagnostic):
    built = subprocess.run([compiler, 'build', DATA / f'{name}.dewy', '-o', tmp_path / 'out',
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode != 0
    assert diagnostic in built.stderr, built.stderr


@pytest.mark.parametrize('release', [False, True])
def test_callback_fixed_width(compiler, tmp_path, release):
    if platform.system() != 'Linux' or shutil.which('cc') is None:
        pytest.skip('C callback control requires Linux and a C compiler')
    built = subprocess.run(['cc', '-shared', '-fPIC', DATA / 'archtest.c',
                            '-o', tmp_path / 'libarchtest.so'], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    binary = tmp_path / 'out'
    built = subprocess.run([compiler, 'build', DATA / 'callback_fixed_width.dewy', '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env=dict(os.environ, LD_LIBRARY_PATH=str(tmp_path)),
                         capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '42\n'
