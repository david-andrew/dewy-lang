"""Practical array bounds cannot leak through facts or cached local ranges."""
import subprocess
import re
import pytest
from tests.support import compiler


@pytest.mark.parametrize('alias', ['direct', 'local', 'helper'])
def test_static_array_ceiling_is_removed(compiler, tmp_path, alias):
    expression = {'direct': 'xs.length', 'local': 'n', 'helper': 'length(xs)'}[alias]
    prefix = 'let n=xs.length;' if alias == 'local' else ''
    for disabled in [False, True]:
        source = tmp_path / 'bound.dewy'
        source.write_text(f'''$runtime_checks=false
length=(xs:array<int64>):>int64=>xs.length
f=(xs:array<int64>):>int64=>{{
{prefix}
{{
{'$no_assumed_bounds' if disabled else ''}
return {expression}*16
}}
}}
main=()=>printl(f([1 2 3]))
''')
        result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
        assert (result.returncode != 0) == disabled, result.stderr
        if disabled: assert 'fits int64' in result.stderr


def test_runtime_optout_retains_check_after_length_alias(compiler, tmp_path):
    source = tmp_path / 'alias.dewy'
    source.write_text('''f=(xs:array<int64>):>int64=>{
let n=xs.length
{
$no_assumed_bounds
return n*16
}
}
main=()=>printl(f([1 2 3]))
''')
    result = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'alias'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    body = next(b for b in re.split(r'^fn ', result.stdout, flags=re.M) if b.startswith('f_f_'))
    assert 'checked_mul' in body, body
    ran = subprocess.run([tmp_path / 'alias'], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == '48'


def test_real_length_guard_still_proves_the_store(compiler, tmp_path):
    source = tmp_path / 'guard.dewy'
    source.write_text('''$no_assumed_bounds
$runtime_checks=false
f=(xs:array<int64>):>int64=>{
let n=xs.length
if n <? 100 return n*16
return 0
}
main=()=>printl(f([1 2 3]))
''')
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
