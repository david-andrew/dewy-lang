"""An `int` beyond int64 takes its own branches: facts must keep them live.

An `int` interval's MIN/MAX endpoint may stand for values past int64, so a
comparison against an int64 edge neither kills the far branch nor collapses
the value onto the edge.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def branch(condition: str, setup: str = '') -> str:
    return f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{
    {setup}let i=0
    if {condition} {{ i=5 }}
    XS[i]
}}
main=()=>printl(f(1))'''


REJECTED = {
    'above_max': branch('n >? 9223372036854775807'),
    'max_below': branch('9223372036854775807 <? n'),
    'below_min': branch('n <? -9223372036854775808'),
    'offset': branch('n+1 >? 9223372036854775807'),
    'at_least_not_max': branch('n >=? 9223372036854775807 and n not=? 9223372036854775807'),
    'at_most_not_min': branch('n <=? -9223372036854775808 and n not=? -9223372036854775808'),
    'above_uint64': branch('n >? 18446744073709551615'),
    'above_fixed': branch('n >? w', 'let w:int64=9223372036854775807\n    '),
    'past_max_twice': branch('n >? 9223372036854775806 and n not=? 9223372036854775807'),
    'nested': '''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{
    let i=0
    if n >=? 9223372036854775807 {
        if n =? 9223372036854775807 { i=0 } else { i=5 }
    }
    XS[i]
}
main=()=>printl(f(1))''',
    'loop_exit': '''const XS:array<int64 length=3>=[10 20 30]
f=(start:int):>int64=>{
    let x=start
    loop x <=? 9223372036854775807 { x+=1 }
    XS[if x =? 9223372036854775808 1 else 9]
}
main=()=>printl(f(1))''',
    'loop_body': '''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{
    let i=0
    let m=n
    loop m >? 9223372036854775807 { m-=1 i=5 }
    XS[i]
}
main=()=>printl(f(1))''',
    'ordered_pair': '''f=(x:int y:int):>int64=>{
    if x >=? 0 and x <? y { return int64(x) }
    0
}
main=()=>printl(f(1 2))''',
}

# The edges that are real stay exact: equality with an int64 edge, a fixed
# width's own edge (also of an unmodeled int64), and uint64's zero.
PROVED = {
    'equal_max': ('''f=(n:int):>int64=>{
    if n =? 9223372036854775807 return int64(n)
    0
}
main=()=>printl(f(9223372036854775807) f(9223372036854775808))''', '9223372036854775807 0\n'),
    'fixed_not_max': ('''f=(x:int64):>int64=>{
    if x =? 9223372036854775807 return 0
    x+1
}
main=()=>printl(f(9223372036854775807) f(4))''', '0 5\n'),
    'fixed_unmodeled': ('''f=(i:int64 a:int64 b:int64):>int64=>{
    if i <? (a xor b) return i+1
    0
}
main=()=>printl(f(1 2 4) f(9 2 4))''', '2 0\n'),
    'unsigned_nonzero': ('''f=(h:uint64 n:uint64):>uint64=>{
    if n =? 0 return 0
    h%n
}
main=()=>printl(f(18446744073709551615 10) f(3 0))''', '5 0\n'),
}


QUICK = {'at_least_not_max', 'loop_exit'}


@pytest.mark.parametrize('name', [pytest.param(name, marks=pytest.mark.core_quick) if name in QUICK else name for name in REJECTED])
def test_int_beyond_int64_branch_is_live(compiler, tmp_path, name):
    path = tmp_path / 'beyond.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    output = checked.stdout + checked.stderr
    assert checked.returncode != 0, output
    expected = 'conversion to int64' if name == 'ordered_pair' else 'index is'
    assert expected in output, output


@pytest.mark.core_quick
@pytest.mark.parametrize('name', PROVED)
def test_int_real_edges_stay_exact(compiler, tmp_path, name):
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
