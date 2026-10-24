"""Stored remainder and mask ranges survive arithmetic consumers."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_small_stored_ranges(compiler, tmp_path, release):
    values = [-2**63, -1001, -1, 0, 999, 2**63-1]
    source = tmp_path / 'main.dewy'
    source.write_text('''remainder=(x:int64):>int64=>{
    $runtime_checks=false
    return (x%1000)-500
}
mask=(x:int64):>int64=>{
    $runtime_checks=false
    return (x&255)-128
}
''' + '\n'.join(f'printl(remainder({x}) mask({x}))' for x in values))
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f'{x%1000-500} {(x&255)-128}' for x in values]
