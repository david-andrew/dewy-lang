"""Large fact scopes retain snapshots, late reads, captures and deferred uses."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_large_scope_live_values(compiler, tmp_path, release):
    source = tmp_path / 'scope.dewy'
    padding = '\n'.join(f'let unused{i}:int64={i}\nif unused{i} >? 0 {{let copy=unused{i}+1}}' for i in range(80))
    source.write_text('''$runtime_checks
f=(xs:array<int64>):>int64=>{
 if xs.length =? 0 return 0
 let saved=xs.length
 let copy=xs
 let answer=()=>copy[saved-1]
 ''' + padding + '''
 $runtime_assert(saved =? copy.length)
 return answer()
}
printl(f([3 7 11]))
''')
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '11\n'
