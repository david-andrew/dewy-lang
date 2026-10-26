"""An `int`'s open MIN/MAX end is infinite through arithmetic, min/max, bit
operations and affine comparisons; a real int64 edge stays exact.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

MAX = '9223372036854775807'
MIN = '-9223372036854775808'


def branch(condition: str, setup: str = '') -> str:
    return f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{
    let i=0
    {setup}
    if {condition} {{ i=50000000000 }}
    XS[i]
}}
main=()=>printl(f(2^70))'''


REJECTED = {
    'minus_one': branch('n >=? 0 and n-1 >? 9223372036854775806'),
    'plus_negative': branch('n >=? 0 and n+(-5) >? 9223372036854775802'),
    'negate': branch(f'n >=? 0 and -n <? {MIN}'),
    'times_minus_one': branch(f'n >=? 0 and n*(-1) <? {MIN}'),
    'below_plus_one': branch(f'n <=? 0 and n+1 <? {MIN}'),
    'offset_back': branch(f'n >=? 0 and (n-1)+1 >? {MAX}'),
    'max_of': branch(f'max(n {MAX}) >? {MAX}'),
    'min_of': branch(f'min(n {MIN}) <? {MIN}'),
    'or_mask': branch(f'n >=? 0 and (n or {MAX}) >? {MAX}'),
    'affine_equal': branch(f'n >? {MAX} and q not=? {MAX}', 'let q=n*1'),
    'affine_above': branch(f'n >? {MAX} and q >? {MAX}', 'let q=n*1'),
    'affine_at_least': branch(f'n >=? {MAX} and q >? {MAX}', 'let q=n+0'),
    'affine_nested': '''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{
    let i=0
    let q=n*1
    if n >? 9223372036854775807 { if q =? 9223372036854775807 { i=0 } else { i=50000000000 } }
    XS[i]
}
main=()=>printl(f(2^70))''',
    'range_counter': '''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{
    let i=0
    loop k in [9223372036854775805..n) { if k-1 >? 9223372036854775806 { i=50000000000 } }
    XS[i]
}
main=()=>printl(f(9223372036854775810))''',
    'narrowed_offset': '''f=(n:int):>int64=>{
    if n <? 1 return 0
    let w:int64=int64(n-1)
    w+1
}
main=()=>printl(f(2^63))''',
}

PROVED = {
    'between_edges': (f'''f=(n:int):>int64=>{{
    if n >=? {MAX} and n <=? {MAX} return int64(n)
    0
}}
main=()=>printl(f({MAX}) f(2^70))''', f'{MAX} 0\n'),
    'between_index': (f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{
    if n >=? {MAX} and n <=? {MAX} return XS[n-{MAX}]
    0
}}
main=()=>printl(f({MAX}))''', '10\n'),
    'between_dead': (f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int):>int64=>{{
    let i=0
    if n >=? {MAX} and n <=? {MAX} and n not=? {MAX} {{ i=50000000000 }}
    XS[i]
}}
main=()=>printl(f({MAX}))''', '10\n'),
    'below_fixed': (f'''f=(n:int w:int64):>int64=>{{
    if n >=? {MAX} and n <=? w return int64(n)
    0
}}
main=()=>printl(f({MAX} {MAX}) f(2^70 {MAX}))''', f'{MAX} 0\n'),
    'joined_guard': (f'''const XS:array<int64 length=3>=[10 20 30]
f=(n:int w:int64):>int64=>{{
    let x=0
    if n <=? w and n >=? 0 {{ x=n }} else {{ x=0 }}
    let i=0
    if x >? {MAX} {{ i=50000000000 }}
    XS[i]
}}
main=()=>printl(f(3 5))''', '10\n'),
}


@pytest.mark.parametrize('name', [pytest.param(name, marks=pytest.mark.core_quick) if name == 'minus_one' else name for name in REJECTED])
def test_int_open_end_rejected(compiler, tmp_path, name):
    path = tmp_path / 'open.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    output = checked.stdout + checked.stderr
    assert checked.returncode != 0, output
    expected = 'conversion to int64' if name == 'narrowed_offset' else 'index is'
    assert expected in output, output


@pytest.mark.parametrize('name', [pytest.param(name, marks=pytest.mark.core_quick) if name == 'between_edges' else name for name in PROVED])
def test_int_real_edge_proves(compiler, tmp_path, name):
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
