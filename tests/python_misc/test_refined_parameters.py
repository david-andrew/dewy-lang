"""Refined parameters as call-site obligations and body facts; the nonzero-divisor obligation."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError

PERCENT = 'let percent = (part:int64 whole:int64<i => i >? 0>):>int64 => part * 100 // whole\n'


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_call_site_obligations() -> None:
    _compile(PERCENT + 'let a = percent(1 4)\n')  # a constant proves it at check time
    # the refuted reading is reported inside the call-vs-product ambiguity report
    with pytest.raises((TypeCheckError, UserError), match='refinement refuted'):
        _compile(PERCENT + 'let a = percent(1 0)\n')
    with pytest.raises(UserError, match='cannot prove refinement') as info:
        _compile(PERCENT + 'let f = (whole:int64):>int64 => percent(1 whole)\n')
    assert 'neither proven nor refuted' in str(info.value)
    _compile(PERCENT + 'let f = (whole:int64):>int64 => { if whole >? 0 { return percent(1 whole) }  return 0 }\n')
    _compile(PERCENT + 'let f = (whole:int64):>int64 => { $runtime_assert whole >? 0  return percent(1 whole) }\n')
    _compile(PERCENT + 'let main = ():>int64 => { let total:int64 = 0  loop k in 1..3 { total += percent(1 k) }  return total }\n')


def test_refinements_are_facts_inside_the_body() -> None:
    _compile('let f = (d:int64<i => i not=? 0>):>int64 => 10 // d\n')
    _compile('let f = (d:int64<i => i >? 0>):>int64 => 10 % d\n')
    _compile('let f = (xs:array<int64 length>?0>):>int64 => xs[0]\n')
    with pytest.raises(UserError, match='array index is not proven'):
        _compile('let f = (xs:array<int64 length>?0>):>int64 => xs[1]\n')


def test_division_needs_a_nonzero_divisor() -> None:
    for operator in ('//', '%'):
        with pytest.raises(UserError, match='cannot prove the divisor is nonzero') as info:
            _compile(f'let f = (n:int64 d:int64):>int64 => n {operator} d\n')
        assert '`d` has no known bound' in str(info.value)
        _compile(f'let f = (n:int64 d:int64):>int64 => {{ if d not=? 0 {{ return n {operator} d }}  return 0 }}\n')
        _compile(f'let f = (n:int64 d:int64):>int64 => {{ if d =? 0 {{ return 0 }}  return n {operator} d }}\n')
        _compile(f'let f = (n:int64 d:int64):>int64 => {{ if d <? 0 {{ return n {operator} d }}  return 0 }}\n')
    # a `not=? 0` fact dies with reassignment
    with pytest.raises(UserError, match='cannot prove the divisor is nonzero'):
        _compile('let f = (n:int64 d:int64 e:int64):>int64 => { if d not=? 0 { d = e  return n // d }  return 0 }\n')


def test_member_routes_and_literal_elements_carry_facts() -> None:
    _compile(
        'let Ratio:type = [top:int64 bottom:int64]\n'
        'let f = (r:Ratio):>int64 => { if r.bottom >? 0 { return r.top // r.bottom }  return 0 }\n'
    )
    with pytest.raises(UserError, match='cannot prove the divisor is nonzero'):
        _compile(
            'let Ratio:type = [top:int64 bottom:int64]\n'
            'let f = (r:Ratio):>int64 => { if r.bottom >? 0 { r.bottom = 0  return r.top // r.bottom }  return 0 }\n'
        )
    # iterating a never-mutated literal bounds the loop variable
    _compile('let main = ():>int64 => { let total:int64 = 0  loop k in [3 5] { total += 10 % k }  return total }\n')
    _compile('let keys:dict<int64 string> = [3 -> "a" 5 -> "b"]\nlet main = ():>int64 => { let total:int64 = 0  loop [k v] in keys { total += 10 % k }  return total }\n')
    with pytest.raises(UserError, match='cannot prove the divisor is nonzero'):
        _compile('let main = ():>int64 => { let xs:array<int64> = [3 5]  xs.push(0)  let total:int64 = 0  loop k in xs { total += 10 % k }  return total }\n')
