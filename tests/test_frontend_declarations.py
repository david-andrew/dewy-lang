"""Direct declaration construction preserves type spellings and fallback."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_direct_declarations(compiler, tmp_path, release):
    source = tmp_path / 'declarations.dewy'
    source.write_text('''const base=40
let global:int64=1
main=()=>{
    let result:int64=base+global
    const extra=1
    let local:int64=result+extra
    let optional:int64?=none
    let wide:int64
    return local
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


@pytest.mark.core_quick
@pytest.mark.parametrize('declaration', ['const value', 'let value + 1',
    'let value[1]', 'let value:int64 + 1', 'let value:uint=1',
    'let value:array<int64>=[1 2]', 'let value:<(a:int64):>int64>=(a:int64)=>a',
    'let value:int64=1 +', 'let value:return=1', 'value:int64=1'])
def test_declaration_fallback(compiler, tmp_path, declaration):
    source = tmp_path / 'fallback.dewy'
    source.write_text(f'main=()=>{{{declaration}\nreturn 0}}\n')
    results = []
    for mode in ('old', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1]
