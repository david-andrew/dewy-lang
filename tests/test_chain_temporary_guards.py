"""Guards written as comparison chains with held operands, and nonzero rational bases."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    # `-1000` is no plain operand: the chain holds it in a temporary
    'negative_chain_return': ('''f=(n:int):>int64=>{
    if not (-1000 <=? n <=? 1000) return 0
    n
}
main=()=>printl(f(-7) f(5000))''', '-7 0\n'),
    'negative_chain_branch': ('''f=(n:int64):>int32=>{
    if -1 <=? n <=? 1000 return n
    0
}
main=()=>printl(f(-1) f(2000))''', '-1 0\n'),
    'negative_strict_index': ('''f=(xs:array<int> i:int64):>int=>{
    if -1 <? i <? xs.length return xs[i]
    0
}
main=()=>printl(f([4 5 6] 2) f([4 5 6] -1))''', '6 0\n'),
    'rational_base_tested': ('''f=(base:rational n:int64):>rational=>{
    if base =? 0 return 0
    base ^ n
}
main=()=>printl(f(2 -3) f(0 -1) f(1/2 2))''', '1/8 0 1/4\n'),
    'rational_base_nested': ('''f=(base:rational n:int64):>rational=>{
    if n <? 0 {
        if base =? 0 return 0
        return base ^ n
    }
    base ^ n
}
main=()=>printl(f(2 -1) f(3 2))''', '1/2 9\n'),
}

REJECTED = {
    # the chain's upper end does not cover int32
    'negative_chain_too_wide': ('''f=(n:int64):>int32=>{
    if -1 <=? n <=? 3000000000 return n
    0
}''', '2147483647'),
    # outside the chain's guarded branch
    'negative_chain_other_path': ('''f=(n:int):>int64=>{
    if -1000 <=? n <=? 1000 return 0
    n
}''', 'int64'),
    'negative_inclusive_index': ('''f=(xs:array<int> i:int64):>int=>{
    if -1 <=? i <? xs.length return xs[i]
    0
}''', 'index'),
    # a negative exponent of an untested rational
    'rational_base_untested': ('''f=(base:rational n:int64):>rational=>base ^ n''', 'exponent'),
    # the base tested is not the base raised
    'rational_other_base': ('''f=(a:rational b:rational n:int64):>rational=>{
    if a =? 0 return 0
    b ^ n
}''', 'exponent'),
    # an integer base still needs a nonnegative exponent
    'integer_base': ('''f=(base:int n:int64):>int=>{
    if base =? 0 return 0
    base ^ n
}''', 'exponent'),
}


@pytest.mark.parametrize('name', PROVED)
def test_chain_temporary_guards_prove(compiler, tmp_path, name):
    source, expected = PROVED[name]
    path = tmp_path / 'proof.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', '--obligations', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'runtime check:' not in checked.stdout
    out = tmp_path / 'proof'
    built = subprocess.run([compiler, 'build', path, '-o', out], text=True, capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_chain_temporary_guards_reject(compiler, tmp_path, name):
    source, word = REJECTED[name]
    path = tmp_path / 'near.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'cannot prove' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
    assert word in checked.stdout + checked.stderr, checked.stdout + checked.stderr
