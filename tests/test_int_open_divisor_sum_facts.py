"""An open `int` end bounds neither a quotient by it nor a wide int64 sum
compared with it; real int64 ends still prove.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

MAX = '9223372036854775807'
MIN = '-9223372036854775808'


def branch(condition: str) -> str:
    return f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{ let i=0  if {condition} {{ i=50000000000 }}  XS[i] }}
main=()=>printl(f(2^70))'''


def stored_sum(condition: str, arguments: str) -> str:
    return f'''f=(a:int64 b:int64 m:int):>int64=>{{ if {condition} {{ let s:int64 = a+b  return s }}  0 }}
main=()=>printl(f({arguments}))'''


REJECTED = {
    'max_over_open': (branch(f'n >=? 1 and ({MAX} // n) <? 1'), 'index is'),
    'min_over_open': (branch(f'n >=? 1 and (({MIN}) // n) >? -2'), 'index is'),
    'sum_below': (stored_sum('a >=? 0 and b >=? 0 and a+b <? m', f'{MAX} {MAX} 2^70'), 'exact integer result fits int64'),
    'sum_at_most': (stored_sum('a >=? 0 and b >=? 0 and a+b <=? m', f'{MAX} {MAX} 2^70'), 'exact integer result fits int64'),
    'sum_flipped': (stored_sum('a >=? 0 and b >=? 0 and m >? a+b', f'{MAX} {MAX} 2^70'), 'exact integer result fits int64'),
    'sum_equal': (stored_sum('a >=? 0 and b >=? 0 and a+b =? m', f'{MAX} {MAX} 2^64-2'), 'exact integer result fits int64'),
    'sum_above': (stored_sum('a <=? 0 and b <=? 0 and a+b >? m', f'({MIN}) ({MIN}) (-2^70)'), 'exact integer result fits int64'),
    'sum_branch': (f'''const XS:array<int64 length=3>=[10 20 30]
f=(a:int64 b:int64 m:int):>int64=>{{ let i=0  if a >=? 0 and b >=? 0 and a+b <? m and a+b >? {MAX} {{ i=50000000000 }}  XS[i] }}
main=()=>printl(f({MAX} {MAX} 2^70))''', 'index is'),
}

PROVED = {
    'small_over_positive': (f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{ let i=0  if n >=? 1 and (5 // n) <? 0 {{ i=50000000000 }}  XS[i] }}
main=()=>printl(f(2^70) f(2))''', '10 10\n'),
    'sum_below_fixed': ('''f=(a:int64 b:int64 m:int64):>int64=>{ if a >=? 0 and b >=? 0 and a+b <? m { let s:int64 = a+b  return s }  0 }
main=()=>printl(f(2 3 10))''', '5\n'),
    'int_copy_product': (f'''f=(x:int64):>int64=>{{ let n:int=x  let q=n*1  if n <? {MAX} and q <? {MAX} return int64(q+1)  0 }}
main=()=>printl(f(5) f({MAX}))''', '6 0\n'),
}


@pytest.mark.parametrize('name', [pytest.param(name, marks=pytest.mark.core_quick) if name == 'sum_below' else name for name in REJECTED])
def test_int_open_end_rejected(compiler, tmp_path, name):
    source, expected = REJECTED[name]
    path = tmp_path / 'open.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    output = checked.stdout + checked.stderr
    assert checked.returncode != 0, output
    assert expected in output, output


@pytest.mark.parametrize('name', PROVED)
def test_int_real_end_proves(compiler, tmp_path, name):
    source, expected = PROVED[name]
    path = tmp_path / 'edge.dewy'
    path.write_text(source + '\n')
    checked = subprocess.run([compiler, 'check', '--obligations', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'runtime check:' not in checked.stdout, checked.stdout
    for flags in ([], ['--release']):
        out = tmp_path / 'edge'
        built = subprocess.run([compiler, 'build', path, '-o', out, *flags], text=True, capture_output=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
        assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr
