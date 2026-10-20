"""Check the existing native-library interface against independently compiled C."""
import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler

FIXTURES = Path(__file__).resolve().parent / 'fixtures/core_ffi'


@pytest.fixture(scope='module')
def variadic_library(tmp_path_factory):
    if platform.system() != 'Linux' or shutil.which('cc') is None:
        pytest.skip('C interoperability checks require Linux and a C compiler')
    library = tmp_path_factory.mktemp('variadic-c') / 'probe.so'
    built = subprocess.run(['cc', '-std=c11', '-O2', '-shared', '-fPIC',
                            FIXTURES / 'variadic.c', '-o', library],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    return library


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['default', 'release', 'debug'])
def test_core_c_variadic_arguments(compiler, tmp_path, variadic_library, mode):
    # A fixed float stays f32; variadic f32 becomes double; narrow integers
    # become int. Ten floats cross the register/stack boundary. An empty
    # variadic tail also remains valid. Exercise the binding from Dewy source.
    binding = tmp_path / 'binding.jo'
    binding.write_text((FIXTURES / 'variadic.jo.in').read_text().replace(
        'LIBRARY', json.dumps(str(variadic_library))))
    source = tmp_path / 'probe.dewy'
    source.write_text('from p"binding.jo" import run_probe\nmain=()=>run_probe()\n')
    binary = tmp_path / 'probe'
    flags = {'default': [], 'release': ['--release'], 'debug': ['-g']}[mode]
    built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)
