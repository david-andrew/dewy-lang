"""Refined results (`:>int64<i => i >=? 1>`) and field invariants (`bottom:int64<bottom >? 0>`)."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError, UserError

REFUTED = (TypeCheckError, UserError)  # refuted at check time from a constant, or by the analysis

POSITIVE = 'let positive = (n:int64):>int64<i => i >=? 1> => { if n >=? 1 { return n }  return 1 }\n'
RATIO = 'let Ratio:type = [top:int64 bottom:int64<bottom >? 0>]\n'


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_refined_results_are_proven_at_returns_and_assumed_at_calls() -> None:
    _compile(POSITIVE + 'let f = (n:int64):>int64 => n // positive(n)\n')
    _compile(POSITIVE + 'let f = (n:int64):>int64 => { let g:int64 = positive(n)  return n // g }\n')
    with pytest.raises(UserError, match='cannot prove refinement') as info:
        _compile('let bad = (n:int64):>int64<i => i >=? 1> => n\n')
    assert 'neither proven nor refuted' in str(info.value)
    with pytest.raises(REFUTED, match='refinement refuted'):
        _compile('let bad = ():>int64<i => i >=? 1> => 0\n')


def test_field_invariants_are_proven_on_construction_and_stores() -> None:
    _compile(RATIO + 'let r = Ratio(1 2)\nlet s:Ratio = [top=3 bottom=4]\n')
    _compile(RATIO + 'let make = (top:int64 bottom:int64):>Ratio => { if bottom >? 0 { return Ratio(top bottom) }  return Ratio(top 1) }\n')
    with pytest.raises(REFUTED, match='refinement refuted'):
        _compile(RATIO + 'let r = Ratio(1 0)\n')
    with pytest.raises(UserError, match='cannot prove refinement'):
        _compile(RATIO + 'let make = (top:int64 bottom:int64):>Ratio => Ratio(top bottom)\n')
    with pytest.raises(UserError, match='cannot prove refinement'):
        _compile(RATIO + 'let main = ():>int64 => { let r = Ratio(1 2)  let z:int64 = 0 transmute int64  r.bottom = z  return 0 }\n')
    _compile(RATIO + 'let main = ():>int64 => { let r = Ratio(1 2)  let z:int64 = 0 transmute int64  if z >? 0 { r.bottom = z }  return 0 }\n')


def test_field_invariants_are_assumed_on_reads() -> None:
    _compile(RATIO + 'let scale = (r:Ratio):>int64 => r.top // r.bottom\n')
    _compile('let main = ():>int64 => { let q = 1 / 3  return 9 // q.denominator }\n')  # the prelude Rational's invariant
    # a plain object is checked against the invariant when it flows into the type
    with pytest.raises(UserError, match='cannot prove refinement'):
        _compile(RATIO + 'let Plain:type = [top:int64 bottom:int64]\nlet scale = (r:Ratio):>int64 => r.top // r.bottom\nlet f = (p:Plain):>int64 => scale(p)\n')
    _compile(RATIO + 'let Plain:type = [top:int64 bottom:int64]\nlet scale = (r:Ratio):>int64 => r.top // r.bottom\nlet f = (p:Plain):>int64 => { if p.bottom >? 0 { return scale(p) }  return 0 }\n')
