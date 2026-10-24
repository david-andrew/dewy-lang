"""Discharging one panic site must preserve every remaining direct failure."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('tail,accepted', [
    ('return xs[xs.length-1]', True),
    ('return xs[i]', False),
    ('panic("still fails")', False),
])
def test_effect_inventory_bounds_restart(compiler, tmp_path, tail, accepted):
    source = tmp_path / 'restart.dewy'
    source.write_text('''$runtime_checks
strict=(xs:array<int64> i:int64):>int64 & no panics=>{
 if xs.length =? 0 return 0
 let first=xs[0]
 ''' + tail + '''
}
main=()=>printl(strict([1 2] 0))
''')
    result = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'restart'],
                            capture_output=True, text=True)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if not accepted:
        assert 'panic' in result.stderr and 'strict' in result.stderr, result.stderr
