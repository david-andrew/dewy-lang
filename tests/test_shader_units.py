"""Physical quantities in shader code: a unit is checked at compilation, so the GPU holds the
plain number (an angle in turns), and sin/cos/tan of an angle become the GPU's of 2π·fract(turns),
in GLSL, SPIR-V and Metal alike."""
import os
import shutil
import subprocess

import pytest

from tests.core_glsl_driver import DriverUnavailable, ShaderDriver
from tests.support import compiler

PROGRAM = r'''from units import turn, rad, m
Vertex:type=[pos:vec4 spin:float32 * Angle]
Params:type=[angle:float32 * Angle tilt:float32 * Angle height:float32 * Length]
Out:type=[pos:vec4 phase:float32 * Angle shade:float32]
wobble=(a:float32 * Angle k:float32):>float32=>sin(a)*k + tan(a/8)
vs=(v:Vertex u:Params):>Out=>{
    let a = v.spin + u.angle
    let lift = u.height/m
    Out(v.pos + vec4(0 lift 0 0) a wobble(a 2.0))
}
fs=(i:Out u:Params):>vec4=>{
    let c = cos(i.phase - u.tilt) * 0.5 + 0.5
    let r = sin(float32(i.shade)*rad)
    vec4(c r float32(i.phase/turn) 1)
}
main=():>void=>exit(entry()) entry=()=>{let source=shader(@vs @fs)
write_text("q.vert" source.vs); write_text("q.frag" source.fs); return 0}
'''


def _env(**extra):
    env = {key: value for key, value in os.environ.items() if not key.startswith('DEWY_')}
    env.update(extra)
    return env


def _build(compiler, tmp_path, *flags, env=None):
    source = tmp_path / 'units_shader.dewy'
    source.write_text(PROGRAM)
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'units_shader', *flags],
                           env=env, capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr


def test_shader_units_glsl(compiler, tmp_path):
    _build(compiler, tmp_path)
    ran = subprocess.run([tmp_path / 'units_shader'], cwd=tmp_path, capture_output=True, text=True,
                         timeout=10, check=False)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    vert, frag = (tmp_path / 'q.vert').read_text(), (tmp_path / 'q.frag').read_text()
    assert 'float spin_;' in vert and 'out float v_phase;' in vert and 'flat' not in vert
    assert 'sin(6.283185307179586 * fract(' in vert and 'tan(6.283185307179586 * fract(' in vert
    assert 'cos(6.283185307179586 * fract(' in frag
    try:
        driver = ShaderDriver()
    except DriverUnavailable:
        return
    try:
        driver.validate(vert, frag)
    finally:
        driver.close()


def test_shader_units_spirv(compiler, tmp_path):
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


def test_shader_units_metal(compiler, tmp_path):
    dump = tmp_path / 'msl'
    dump.mkdir()
    _build(compiler, tmp_path, '--target', 'aarch64-mac', env=_env(DEWY_MSL_DUMP=str(dump)))
    text = ''.join(path.read_text() for path in sorted(dump.glob('*.metal')))
    assert 'sin(6.283185307179586f * fract(' in text and 'cos(6.283185307179586f * fract(' in text
    assert 'float phase_;' in text
