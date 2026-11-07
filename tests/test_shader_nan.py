"""NaN and infinities in shader code, in a named function and an entry: GLSL has no literal
for them, so they are written by their bits; SPIR-V and Metal take their own constants."""
import os
import re
import shutil
import subprocess

import pytest

from tests.core_glsl_driver import DriverUnavailable, ShaderDriver
from tests.support import compiler  # noqa: F401

PROGRAM = r'''Vertex:type=[pos:vec4 w:float32]
Params:type=[k:float32]
Out:type=[pos:vec4 shade:float32]
blank=(x:float32):>float32=>if x >? 1.0 {float32.nan} else {x}
cap=(x:float32):>float32=>if x >? 2.0 {float32.inf} else if x <? -2.0 {-float32.inf} else {x}
vs=(v:Vertex u:Params):>Out=>Out(v.pos blank(cap(v.w * u.k)))
fs=(i:Out _u:Params):>vec4=>{
    let s = if i.shade >? 3.0 {float32.nan} else {i.shade}
    vec4(s 0 0 1)
}
main=():>void=>exit(entry()) entry=()=>{let source=shader(@vs @fs)
write_text("q.vert" source.vs); write_text("q.frag" source.fs); return 0}
'''


def _env(**extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith('DEWY_')}
    env.update(extra)
    return env


def _build(compiler, tmp_path, *flags, env=None):
    source = tmp_path / 'nan_shader.dewy'
    source.write_text(PROGRAM)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'nan_shader', *flags],
                           env=env, capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr


def test_shader_nan_glsl(compiler, tmp_path):
    _build(compiler, tmp_path)
    ran = subprocess.run([tmp_path / 'nan_shader'], cwd=tmp_path, capture_output=True, text=True,
                         timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    vert, frag = (tmp_path / 'q.vert').read_text(), (tmp_path / 'q.frag').read_text()
    for text in (vert, frag):
        assert not re.search(r'\b(nan|inf)\b', text), text
    assert 'uintBitsToFloat(0x7fc00000u)' in vert and 'uintBitsToFloat(0x7fc00000u)' in frag
    assert '(- uintBitsToFloat(0x7f800000u))' in vert
    try:
        driver = ShaderDriver()
    except DriverUnavailable:
        return
    try:
        driver.validate(vert, frag)
    finally:
        driver.close()


def test_shader_nan_spirv(compiler, tmp_path):
    dump = tmp_path / 'spv'
    dump.mkdir()
    _build(compiler, tmp_path, env=_env(DEWY_SPIRV_DUMP=str(dump)))
    modules = sorted(dump.glob('*.spv'))
    assert len(modules) == 2
    validator = shutil.which('spirv-val')
    if not validator:
        pytest.skip('spirv-val is needed to validate the SPIR-V')
    for module in modules:
        checked = subprocess.run([validator, module], capture_output=True, text=True, timeout=30, check=False)
        assert checked.returncode == 0, checked.stdout + checked.stderr


def test_shader_nan_metal(compiler, tmp_path):
    dump = tmp_path / 'msl'
    dump.mkdir()
    _build(compiler, tmp_path, '--target', 'aarch64-mac', env=_env(DEWY_MSL_DUMP=str(dump)))
    text = ''.join(path.read_text() for path in sorted(dump.glob('*.metal')))
    assert 'NAN' in text and 'INFINITY' in text
    assert not re.search(r'\b(nan|inf)\b', text), text
