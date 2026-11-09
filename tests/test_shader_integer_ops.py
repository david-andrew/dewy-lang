"""Integer arithmetic in GPU code without a device: proven fixed-width stores (`x + 1` into an
int32) in the SPIR-V (checked with spirv-val) and Metal text.
(Results on drivers and the CPU fallback: tests/cases/gpu_integer_ops.)"""
import os
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = r'''$runtime_checks
Shift:type=[src:GpuBuffer<int32> dst:GpuBuffer<int32>]
back=(id:int64 u:Shift):>void=>{
    if id >? 0 and id <? 1000000 { u.dst[id]=u.src[id-1] } else { u.dst[id]=u.src[id] }
}
step=(x:int32):>int32=>{
    if x <? 1000 and x >? -1000 {
        let t:int32=x*3-7
        return t & 255
    }
    return 0
}
main=()=>{
    let a=gpu_buffer([int32(-9) 5 -7])
    let b=gpu_buffer<int32>(3)
    dispatch(compute(@back) 3 Shift(a b))
    printl(cpu(b))
    printl(cpu(step.(gpu([int32(-9) 5]))).data)
}
'''


def _build(compiler, tmp_path, *flags, **extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith('DEWY_')}
    env.update(extra)
    source = tmp_path / 'ints.dewy'
    source.write_text(PROGRAM)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'ints', *flags],
                           env=env, capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr


def test_integer_ops_spirv(compiler, tmp_path):
    dump = tmp_path / 'spv'
    dump.mkdir()
    _build(compiler, tmp_path, DEWY_SPIRV_DUMP=str(dump))
    modules = sorted(dump.glob('*.spv'))
    assert modules
    validator = shutil.which('spirv-val')
    if not validator:
        pytest.skip('spirv-val is needed to validate the SPIR-V')
    for module in modules:
        checked = subprocess.run([validator, '--target-env', 'vulkan1.2', module], capture_output=True,
                                 text=True, timeout=30, check=False)
        assert checked.returncode == 0, checked.stdout + checked.stderr


def test_integer_ops_metal(compiler, tmp_path):
    dump = tmp_path / 'msl'
    dump.mkdir()
    _build(compiler, tmp_path, '--target', 'aarch64-mac', DEWY_MSL_DUMP=str(dump))
    assert list(dump.glob('*.metal'))
