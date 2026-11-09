"""Exact `int` values proven to fit in 32 bits (a counting loop over literals, constants and their
sums and products) become shader words, without a device: the SPIR-V is checked with spirv-val and
the Metal and GLSL text built. (Results on drivers and the CPU fallback: tests/cases/gpu_word_memory.)"""
import os
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = r'''$runtime_checks
P:type=[dst:GpuBuffer<float32>]
k=(id:int64 u:P):>void=>{
    if id <? 0 or id >=? u.dst.length { return }
    let s:float32=0.0
    let base=3
    loop i in [0..4) {
        loop j in [1..3] { s += float32(i*base+j-2) }
    }
    u.dst[id]=s
}
f=(x:float32):>float32=>{
    let s:float32=0.0
    loop i in [0..4) { s += x*float32(i) }
    return s
}
main=()=>{
    let b=gpu_buffer<float32>(2)
    dispatch(compute(@k) 2 P(b))
    printl(cpu(b))
    printl(cpu(f.(gpu([float32(1.0) 2.0]))).data)
}
'''


def _build(compiler, tmp_path, *flags, **extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith('DEWY_')}
    env.update(extra)
    source = tmp_path / 'loops.dewy'
    source.write_text(PROGRAM)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'loops', *flags],
                           env=env, capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr


def test_exact_loops_spirv(compiler, tmp_path):
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


def test_exact_loops_metal(compiler, tmp_path):
    dump = tmp_path / 'msl'
    dump.mkdir()
    _build(compiler, tmp_path, '--target', 'aarch64-mac', DEWY_MSL_DUMP=str(dump))
    text = ''.join(path.read_text() for path in sorted(dump.glob('*.metal')))
    assert 'for (' in text, text


def test_exact_loops_web(compiler, tmp_path):
    _build(compiler, tmp_path, '--target', 'wasm32')
