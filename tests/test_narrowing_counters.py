"""Finite int64 values survive hulls, return summaries and loop headers; counted
mathematical-int updates stay within entry + trips * step."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'summary_mixed_returns': ('''g=(t:int64)=>{if t=?3 return 1 return t}
printl(int64(g(-9223372036854775808)) int64(g(9223372036854775807)) int64(g(3)))''', '-9223372036854775808 9223372036854775807 1\n'),
    'conditional_hull': ('''g=(t:int64 c:bool)=>if c 1 else t
printl(int64(g(9223372036854775807 false)) int64(g(5 true)))''', '9223372036854775807 1\n'),
    'joined_local': ('''g=(t:int64 c:bool)=>{let x=0 if c x=t return x}
printl(int64(g(-9223372036854775808 true)) int64(g(5 false)))''', '-9223372036854775808 0\n'),
    'running_maximum': ('''f=(xs:array<int64>):>int64=>{let m=0 let i=0 loop i <? xs.length { m = max(m xs[i]) i+=1 } return m}
printl(f([]) f([3 9223372036854775807 -4]))''', '0 9223372036854775807\n'),
    'running_length_maximum': ('''f=(xs:array<array<int64>>):>int64=>{let m=0 let i=0 loop i <? xs.length { m = max(m xs[i].length) i+=1 } return m}
printl(f([]) f([[1] [1 2 3] []]))''', '0 3\n'),
    'counted_elements': ('''f=(xs:array<string>):>int64=>{let n=0 loop x in xs {if x.length >? 1 n+=1} return n}
printl(f(["a" "bb" "ccc"]))''', '2\n'),
    'counted_decrement': ('''f=(xs:array<int64>):>int64=>{let n=0 loop x in xs {n-=2 if x=?3 break} return n}
printl(f([1 2 3 4]))''', '-6\n'),
    'counted_narrow_steps': ('''f=(xs:array<int8>):>int64=>{let t=0 loop x in xs {t+=x} return t}
printl(f([-128 127 100]))''', '99\n'),
    'counted_range': ('''f=():>int64=>{let t=0 loop i in [0..10) {if i%2=?0 t+=3} return t}
printl(f())''', '15\n'),
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_counters_proved(compiler, tmp_path, name, release):
    source, output = PROVED[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source + '\n')
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == output


REJECTED = {
    'summary_unbounded_arm': 'g=(t:int64 u:int)=>{if t=?3 return u return t}\nprintl(int64(g(3 99999999999999999999)))',
    'hull_unbounded_arm': 'g=(t:int64 u:int c:bool)=>if c u else t\nprintl(int64(g(1 99999999999999999999 true)))',
    'joined_wide_sum': 'g=(t:int64 c:bool)=>{let x=0 if c x=t+t return x}\nprintl(int64(g(9223372036854775807 true)))',
    'loop_sum_of_words': 'f=(xs:array<int64>):>int64=>{let t=0 loop x in xs {t+=x} return t}\nprintl(f([9223372036854775807 1]))',
    'loop_growing_value': 'f=(xs:array<int64>):>int64=>{let m=1 let i=0 loop i <? xs.length { m = m + xs[i] i+=1 } return m}\nprintl(f([9223372036854775807]))',
    'counted_twice': 'f=(xs:array<int64>):>int8=>{let n=0 loop x in xs {n+=100 n+=100} return n}\nprintl(f([1]))',
    'counted_other_write': 'f=(xs:array<int64>):>int64=>{let n=0 loop x in xs {n+=1 if x=?1 n=x*x} return n}\nprintl(f([1]))',
    'counted_wide_step': 'f=(xs:array<int64>):>int64=>{let n=0 loop x in xs {n+=4294967296} return n}\nprintl(f([1]))',
    'counted_unbounded_range': 'f=(k:int64):>int64=>{let t=0 loop i in [0..k) {t+=2} return t}\nprintl(f(3))',
    'counted_small_target': 'f=(xs:array<int64>):>int8=>{let n=0 loop x in xs {n+=1} return n}\nprintl(f([1]))',
}


@pytest.mark.parametrize('name', REJECTED)
def test_counters_still_required(compiler, tmp_path, name):
    path = tmp_path / f'{name}.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True)
    assert checked.returncode != 0, checked.stdout + checked.stderr
    assert 'cannot prove' in checked.stderr or 'does not fit' in checked.stderr, checked.stderr
