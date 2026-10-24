"""Argument contracts do not demand unused returns, but retain effects and dependencies."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_contract_actuals_and_result_length(compiler, tmp_path, release):
    source = tmp_path / 'calls.dewy'
    source.write_text('''
keep=(xs:array<int64> limit:int64 i:int64<0 <=? i and i <? limit>):>array<int64>=>xs
touch=(@x:int64):>int64=>{x=7; return 3}
main=():>void=>{
    let xs:array<int64>=[4 5]
    let changed:int64=0
    keep(xs touch(@changed) 2);
    let ys=keep(xs 3 2)
    $assert ys.length =? 2
    printl(changed)
    printl(ys[1])
}
''')
    output = tmp_path / 'calls'
    built = subprocess.run([compiler, 'build', source, '-o', output,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([output], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout == '7\n5\n', ran.stdout + ran.stderr


@pytest.mark.parametrize('body', [
    'keep(xs 2 2);',
    'let x:int64=1; change(@x 1); $assert x >? 0',
])
def test_contract_only_call_keeps_failures(compiler, tmp_path, body):
    source = tmp_path / 'reject.dewy'
    source.write_text('''
keep=(xs:array<int64> limit:int64 i:int64<0 <=? i and i <? limit>):>array<int64>=>xs
change=(@x:int64 k:int64<k >? 0>):>array<int64>=>{x=0; return []}
main=():>void=>{let xs:array<int64>=[1]; ''' + body + '}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert checked.returncode != 0, checked.stdout + checked.stderr
    assert 'refinement' in checked.stderr or 'assertion' in checked.stderr, checked.stderr
