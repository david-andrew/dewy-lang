"""Direct flow bodies preserve block shape, flags, and fallback contexts."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_direct_flow_identity(compiler, tmp_path, release):
    source = tmp_path / 'flows.dewy'
    source.write_text('''main=():>void=>{
    let total:int64=0
    loop i in [0..4) {
        if i%2=?0 {total+=i}
        else if i=?1 {total+=10}
        else {total+=20}
    }
    let count=0
    loop count <? 2 {count+=1}
    loop false {return} else {total+=count}
    if total=?34 {exit(total+8)} else {return}
}
''')
    images = []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source,
                                 *(['--release'] if release else []), '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        assert subprocess.run([output], timeout=10).returncode == 42
    assert images[0] == images[1]


@pytest.mark.parametrize('statement', ['if true {return 1}',
    'loop false and true {return 1}', 'loop i in [0 1] and j in [2 3] {return i+j}',
    'loop i in [0,2..10) {value+=i}', 'loop i in [0..3) {value+=i} else {value+=2}',
    'if true {value+=1} else if false {value+=2}', 'loop i in [0..3) {value+=}',
    'if true {return', 'loop true {break $missing}'])
def test_flow_fallback_diagnostics(compiler, tmp_path, statement):
    source = tmp_path / 'fallback.dewy'
    source.write_text(f'main=()=>{{let value=0\n{statement}\nreturn value}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
