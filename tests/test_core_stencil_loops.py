"""Shifted stencil indexes can also supply the counting loop's increment."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_stencil_reused_increment(compiler, tmp_path, release):
    source = tmp_path / 'stencil.dewy'
    source.write_text('''
step=(above:array<float64> center:array<float64> below:array<float64>):>array<float64>=>{
 let out=center
 loop j in [1..center.length-1) {
  out[j]=(above[j]+below[j]+center[j-1]+center[j+1])*0.25
 }
 return out
}
main=():>void=>exit(entry()) entry=()=>{
 loop n in [2..35) {
  let a=[loop i in [0..n) (i*i) as float64]
  let b=step(a a a)
  $runtime_assert(b[0] =? a[0] and b[n-1] =? a[n-1])
  loop j in [1..n-1) {$runtime_assert(b[j] =? a[j]+0.5)}
 }
 return 0
}
''')
    output = tmp_path / 'stencil'
    build = subprocess.run([compiler, 'build', source, '-o', output, '--ir',
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    if release:
        assert 'vld ' in build.stdout, build.stdout
    run = subprocess.run([output], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('control', ['if j%3 =? 0 continue', 'if j >? 9 break'])
def test_stencil_control_flow_keeps_scalar_meaning(compiler, tmp_path, control):
    source = tmp_path / 'control.dewy'
    source.write_text('''
main=():>void=>exit(entry()) entry=()=>{
 let a=[loop i in [0..32) i as int64]
 let out=[loop i in [0..32) 0 as int64]
 loop j in [1..31) {
 ''' + control + '''
 out[j]=a[j-1]+a[j+1]
 }
 loop j in [1..31) {
 let skipped=''' + ('j%3 =? 0' if 'continue' in control else 'j >? 9') + '''
 $runtime_assert(out[j] =? (if skipped 0 else 2*j))
 }
 return 0
}
''')
    run = subprocess.run([compiler, '--release', source], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
