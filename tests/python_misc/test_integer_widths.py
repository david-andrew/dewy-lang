"""Integers meeting other widths, plain or inside a union, are proven casts."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_an_integer_meeting_an_optional_word_becomes_that_word() -> None:
    root = _check('let f = (n:int64):>uint64? => {\n    if n >? 0 return n\n    return none\n}')
    body = root.items[0].expr.body   # type: ignore[union-attr]
    guard = body.items[0]
    assert isinstance(guard, hir.Flow)
    returned = guard.arms[0].body.items[0] if isinstance(guard.arms[0].body, hir.Block) else guard.arms[0].body
    assert isinstance(returned, hir.Return) and isinstance(returned.item, hir.ValueCast) and returned.item.type == 'uint64'


def test_a_length_fits_uint64_but_an_unbounded_int64_does_not_fit_int8() -> None:
    _check('let f = (s:string):>uint64 => {\n    let u:uint64 = s.length\n    return u\n}')
    with pytest.raises(UserError, match='cannot prove this integer fits `int8`'):
        _check('let f = (w:int64):>int8 => {\n    let b:int8 = w\n    return b\n}')


def test_widening_a_fixed_width_needs_no_facts() -> None:
    _check('let f = (b:int8):>int64 => {\n    let w:int64 = b\n    return w\n}')


def test_a_string_literal_keeps_its_length_through_a_refined_parameter() -> None:
    _check('let f = (s:string<length >? 0>):>int64 => s.length\nlet n = f("ab")')
    with pytest.raises(UserError, match='length >\\? 0'):
        _check('let f = (s:string<length >? 0>):>int64 => s.length\nlet n = f("")')


def test_a_union_with_two_word_members_stays_a_mismatch() -> None:
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check('let f = (n:int64):>uint8|uint16 => n')
