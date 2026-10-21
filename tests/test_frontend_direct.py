"""Direct value expressions retain the legacy compact AST and diagnostics."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_direct_expression_identity(compiler, tmp_path, release):
    source = tmp_path / 'expressions.dewy'
    source.write_text('''Point:type=[x:int64 y:int64]
twice=(x:int64):>int64=>x*2
main=()=>{
    let point=Point[10 11]
    let values=[1 2 3]
    let callback=(x:int64):>int64=>x+1
    let unused=2(3+4)^2
    let signed_zero=-0.0
    let a=twice(x=point.x)
    let b=values[end-1]
    let c=callback(b)
    let text="item {c}"
    if a >? 0 and not false {
        return twice((point.x+point.y))
    }
    return 0
}
''')
    output = tmp_path / 'expressions'
    images = []
    for mode in ('old', 'compare'):
        built = subprocess.run([compiler, 'build', source, *(['--release'] if release else []), '-o', output],
                               env=dict(os.environ, DEWY_FRONTEND=mode),
                               capture_output=True, text=True, timeout=30)
        assert built.returncode == 0, built.stdout + built.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 42, ran.stdout + ran.stderr
    assert images[0] == images[1]


@pytest.mark.parametrize('expression', ['f(1 +)', '1e+', '1 + (2 *', '1[none]', 'type of 2'])
def test_direct_expression_diagnostics(compiler, tmp_path, expression):
    source = tmp_path / 'invalid.dewy'
    source.write_text(f'main=()=>{{return {expression}}}\n')
    results = []
    for mode in ('old', 'compare'):
        result = subprocess.run([compiler, 'check', source], env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0][0] != 0
    assert results[0] == results[1]
