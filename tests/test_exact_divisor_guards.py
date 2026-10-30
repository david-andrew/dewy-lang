"""`rational(n d)` takes a guarded denominator; an exact power of a positive base is positive."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'guarded_denominator': ('''f=(a:int d:int):>rational=>{
    if d =? 0 return 0
    rational(a d)
}
main=()=>printl(f(1 3) f(2 0))''', '1/3 0\n'),
    'literal_denominator': ('''main=()=>printl(rational(2 5) rational(7))''', '2/5 7\n'),
    'power_of_ten': ('''f=(a:int k:int64):>rational=>{
    if not (0 <=? k <=? 18) return 0
    rational(a 10 ^ k)
}
main=()=>printl(f(25 2) f(3 0))''', '1/4 3\n'),
    'power_divisor': ('''f=(k:int64):>int=>{
    if k <? 0 return 0
    1000 // (2 ^ k)
}
main=()=>printl(f(3) f(20))''', '125 0\n'),
    'negative_base_nonzero': ('''f=(k:int64):>int=>{
    if k <? 0 return 0
    64 // ((-2) ^ k)
}
main=()=>printl(f(3) f(2))''', '-8 16\n'),
    'text_parts': ('''main=()=>printl(rational("3" "4") ?? 0)''', '3/4\n'),
}

REJECTED = {
    'unguarded_denominator': '''f=(a:int d:int):>rational=>rational(a d)''',
    'other_guard': '''f=(a:int d:int):>rational=>{
    if a =? 0 return 0
    rational(a d)
}''',
    'unknown_power_base': '''f=(b:int k:int64):>int=>{
    if k <? 0 return 0
    100 // (b ^ k)
}''',
    'zero_power_base': '''f=(k:int64):>rational=>{
    if k <? 0 return 0
    rational(1 0 ^ k)
}''',
}


@pytest.mark.parametrize('name', PROVED)
def test_exact_divisor_guards_prove(compiler, tmp_path, name):
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
def test_exact_divisor_guards_reject(compiler, tmp_path, name):
    path = tmp_path / 'near.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'nonzero' in checked.stdout + checked.stderr, checked.stdout + checked.stderr


def test_unproven_denominator_checks_at_run_time(compiler, tmp_path):
    path = tmp_path / 'checked.dewy'
    path.write_text('$runtime_checks\nf=(a:int d:int):>rational=>rational(a d)\nmain=()=>printl(f(1 0))\n')
    out = tmp_path / 'checked'
    built = subprocess.run([compiler, 'build', path, '-o', out], text=True, capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 101, ran.stdout + ran.stderr
