"""Check the existing native-library interface against independently compiled C."""
import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.python_misc.test_sloppy_core import compiler

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/core_ffi'


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


@pytest.mark.core_quick
def test_core_host_variadic_signature(tmp_path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or not shutil.which('cc'):
        pytest.skip('optional C compiler host requires Linux x86-64 and cc')
    from tools.sloppy_core.c_host import translate
    # Test the exported call convention directly: the host translator does
    # not implement the native dynamic-loader trampoline. Arguments here are
    # already promoted by lowering, as in actual exported compiler IR.
    source = tmp_path / 'variadic.ir'
    source.write_text("""DEWY_HOST_IR 1
FN 0 7 0 false
NAME probe
VT [0,2,0,1,1,0,0,0]
KV []
SS []
SA []
ARGS [1,2,3,4,5,6]
I callc 0 7 0 6 0 3
I ret 0 -1 7 -1 -1 0
END
META 8 -1 false -1 -1
ROOTS []
DATA []
""")
    generated = tmp_path / 'c'
    manifest = translate(source, generated)
    harness = generated / 'probe.c'
    harness.write_text("""#include "host.h"
#include <assert.h>
int64_t check_mix(float, int64_t, ...);
int main(void) {
    assert(dw_0_probe((U)check_mix, 2.5f, 7, 1.25, 3.75, (U)-7, 250) == 42);
    return 0;
}
""")
    binary = tmp_path / 'probe'
    units = [generated / name for name in manifest['units'] if name != 'runtime.c']
    built = subprocess.run(['cc', '-O2', '-fno-strict-aliasing', *units, harness,
                            FIXTURES / 'variadic.c', '-lm', '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
