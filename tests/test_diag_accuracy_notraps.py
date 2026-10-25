"""Text targets from the no-traps diagnostic accuracy review.

These programs must remain rejected, and each diagnostic must name the missing
relation or give a concrete repair. A strict xfail marks a target not yet met.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


CASES = {
    'int_counter_in_loop': (
        'f=(xs:array<int>):>int64=>{let sum=0 loop x in xs {sum+=x} return sum}\nprintl(f([1]))',
        'error: cannot prove `sum <=? 9223372036854775807` for the conversion to int64: missing upper bound'),
    'unbounded_dividend': (
        'f=(n:int):>int64=>(n-1)//7+1\nprintl(f(1))',
        'error: cannot prove `(n - 1) // 7 + 1 <=? 9223372036854775807` for the conversion to int64: missing upper bound'),
    'unbounded_sum': (
        'f=(n:int m:int):>int64=>(n+m)//7\nprintl(f(1 2))',
        'error: cannot prove `(n + m) // 7 <=? 9223372036854775807` for the conversion to int64: missing upper bound'),
    'zero_start_divisor': (
        'f=(n:int64):>bool=>{let d:int64=0 loop d*d <=? n {if n % d =? 0 return false d+=1} true}\nprintl(f(10))',
        'error: cannot prove divisor is nonzero: missing bound'),
    'truncate_unknown_count': (
        'f=(n:int64):>void=>{let xs:array<int64 length >? 0>=[1 2] xs.truncate(n) printl(xs)}\nf(0)',
        'help: establish `n >=? 0` before `xs.truncate(n)`'),
    'borrowed_divisor_after_call': (
        'S:type=[count:int64]\nzero=(@x:int64):>void=>{x=0}\n'
        'main=()=>{let m=mutex(dict<string S>[]) let d=@(m.lock()) d["x"]=S[2] '
        'if d["x"].count =? 0 {return} zero(@d["x"].count) printl(10/d["x"].count)}',
        'help: establish `d["x"].count not=? 0` after `zero(@d["x"].count)`'),
    'loop_iterable_fallback': (
        'main=()=>{let a:array<int64>|none=none let b:array<int64>=[1] '
        'loop x in a ?? b {printl(x)}}',
        'error: parenthesize the fallback in the loop iterable: `loop x in (a ?? b)`'),
    'union_alias': (
        'Value:type=int64|string\nf=(v:Value):>int64=>v\nprintl(f(1))',
        'error: type mismatch: expected int64, found Value'),
}


# (the loop header is read by the direct parser, whose readers are being moved)
PENDING = {'loop_iterable_fallback'}


@pytest.mark.core_quick
@pytest.mark.parametrize('name', [
    pytest.param(name, marks=pytest.mark.xfail(reason='diagnostic text does not yet give the repair', strict=True))
    if name in PENDING else name for name in CASES])
def test_diagnostic_text_target(compiler, tmp_path, name):
    source, expected = CASES[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source + '\n')
    result = subprocess.run(
        [compiler, '--internal-fact-policy=require-static', 'check', path],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert expected in result.stderr, result.stderr
