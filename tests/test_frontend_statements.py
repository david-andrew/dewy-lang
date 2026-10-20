"""Statement construction preserves ASTs, diagnostics and emitted images."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_direct_statements(compiler, tmp_path, release):
    source = tmp_path / 'statements.dewy'
    source.write_text('''main=()=>{
    let value:int64=7
    value+=5
    value*=3
    value//=2
    value%=11
    value^=2
    value<<=1
    value>>=1
    $outer
    loop true {
        value-=1
        if value=?48 {continue $outer}
        break $outer
    }
    return value;
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
        assert subprocess.run([output], timeout=10).returncode == 47
    assert images[0] == images[1]


@pytest.mark.core_quick
@pytest.mark.parametrize('statement', ['return 1 +', 'value += (2 *', 'break $missing',
                                       'value = [1; 2]', 'return', 'continue $missing'])
def test_statement_diagnostics(compiler, tmp_path, statement):
    source = tmp_path / 'invalid.dewy'
    source.write_text(f'main=()=>{{let value=0\n{statement}}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]


@pytest.mark.core_quick
@pytest.mark.parametrize('body', ['return value+1', 'value+=1', 'value=1'])
def test_statement_record_sibling_scope(compiler, tmp_path, body):
    source = tmp_path / 'sibling.dewy'
    source.write_text('Counter:type=[value:int64 get=()=>{' + body + '} ]\n'
                      'main=()=>{let c=Counter(40) return c.get}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
