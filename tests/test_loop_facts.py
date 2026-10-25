"""Array and range loops iterate their headers to a fixed point; an integer
comprehension has an element hull; dictionary and set entry counts are
lengths; a successful text search is at most the text's length; a call's
diagnostic names the call."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'array_running_maximum': ('''f=(xs:array<int64>):>int64=>{let m=0 loop x in xs { m = max(m x) } return m}
printl(f([]) f([3 9223372036854775807 -4]))''', '0 9223372036854775807\n'),
    'array_running_length_maximum': ('''f=(xs:array<array<int64>>):>int64=>{let m=0 loop x in xs { m = max(m x.length) } return m}
printl(f([]) f([[1] [1 2 3] []]))''', '0 3\n'),
    'range_running_minimum': ('''f=(xs:array<int64>):>int64=>{let m=0 loop i in [0..xs.length) { m = min(m xs[i]) } return m}
printl(f([]) f([3 -9223372036854775808 4]))''', '0 -9223372036854775808\n'),
    'comprehension_elements': ('''f=():>int8=>{let xs = [loop x in [1 2 3] x] let t:int8=0 loop x in xs { t = x } return t}
printl(f())''', '3\n'),
    'filtered_comprehension': ('''f=(ys:array<int64>):>int8=>{let xs = [loop y in ys if 0 <? y <? 100 y] let t:int8=0 loop x in xs { t = x } return t}
printl(f([5 -2 300 7]))''', '7\n'),
    'range_comprehension_read': ('''f=():>int8=>{let xs = [loop i in [0..10) i*2] if xs.length >? 3 return xs[3] return 0}
printl(f())''', '6\n'),
    'dictionary_length_guard': ('''f=(d:dict<string int64>):>int32=>{if d.length <? 10 return d.length return 0}
printl(f(["a"->1 "b"->2]))''', '2\n'),
    'set_length_guard': ('''f=(d:set<int64>):>int32=>{if d.length <? 10 return d.length return 0}
printl(f(set[4 5 4]))''', '2\n'),
    'dictionary_length_sum': ('''f=()=>{let a=["a"->1 "b"->2] return a.length+40}
printl(int64(f()))''', '42\n'),
    'text_find_successor': ('''f=(s:string):>int64=>{let close = s.find(")") if close is? Missing return 0 return close + 1}
g=(s:string):>int64=>{let close = s.rfind(")") if close is? Missing return 0 let i = close + 1 return i}
h=(s:string):>string=>{let close = s.find(")") if close is? Missing return "" return s[0..close)}
printl(f("ab)") g("a)b)") h("ab)c") f("é)"))''', '3 4 ab 2\n'),
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_loop_facts_proved(compiler, tmp_path, name, release):
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
    'array_running_sum': 'f=(xs:array<int64>):>int64=>{let m=0 loop x in xs { m = m + x } return m}\nprintl(f([9223372036854775807 1]))',
    'array_running_unbounded_maximum': 'f=(xs:array<int>):>int64=>{let m=0 loop x in xs { m = max(m x) } return m}\nprintl(f([1]))',
    'array_loop_break_value': 'f=(xs:array<int64>):>int64=>{let m=0 loop x in xs { m = max(m x) if x =? 3 { m = 99999999999999999999 break } } return m}\nprintl(f([3]))',
    'hull_of_unbounded_values': 'f=(ys:array<int64>):>int8=>{let xs = [loop z in ys z] let t:int8=0 loop x in xs { t = x } return t}\nprintl(f([1000]))',
    'hull_after_element_write': 'f=(ys:array<int64> y:int64):>int8=>{let xs = [loop z in ys 1] if xs.length >? 0 xs[0] = y let t:int8=0 loop x in xs { t = x } return t}\nprintl(f([1] 1000))',
    'hull_after_alias_write': 'f=(ys:array<int64> y:int64):>int8=>{let xs = [loop z in ys 1] loop @q in xs { q = y } let t:int8=0 loop x in xs { t = x } return t}\nprintl(f([1] 1000))',
    'hull_after_push': 'f=(y:int64):>int8=>{let xs = [loop x in [1 2 3] x] xs.push(y) let t:int8=0 loop x in xs { t = x } return t}\nprintl(f(1000))',
    'hull_after_extend': 'f=(ys:array<int64> y:int64):>int8=>{let xs = [loop z in ys 1] xs.extend([y]) let t:int8=0 loop x in xs { t = x } return t}\nprintl(f([2] 1000))',
    'dictionary_length_after_insert': 'f=(d:dict<string int64>):>int32=>{let e = d if e.length <? 10 { e["z"] = 1 return e.length } return 0}\nprintl(f(["a"->1]))',
    'text_find_not_an_index': 'f=(s:string):>string=>{let close = s.find(")") if close is? Missing return "" return s[close]}\nprintl(f("ab)"))',
}


@pytest.mark.parametrize('name', REJECTED)
def test_loop_facts_still_required(compiler, tmp_path, name):
    path = tmp_path / f'{name}.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True)
    assert checked.returncode != 0, checked.stdout + checked.stderr
    assert 'cannot prove' in checked.stderr or 'does not fit' in checked.stderr, checked.stderr


def test_call_result_named(compiler, tmp_path):
    path = tmp_path / 'call.dewy'
    path.write_text('f=(a:int b:int):>int=>a*b\nlet y:int64=f(3 4)\nprintl(y)\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True)
    assert checked.returncode != 0
    assert 'cannot prove `f(3 4) <=? 9223372036854775807` for the conversion to int64' in checked.stderr, checked.stderr
