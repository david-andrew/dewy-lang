"""Widened loop counters narrow back to what the guard admits."""
import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_an_abstract_counter_under_a_length_guard_fits_a_word() -> None:
    _check('let f = (src:string):>int64 => {\n    i = 0\n    loop i <? src.length { i += 1 }\n    return i\n}')
    _check('let f = (src:string):>int64 => {\n    i = 0\n    loop i <? src.length { if src[i] =? "a" i += 2 else i += 1 }\n    return i\n}')


def test_an_abstract_counter_under_a_word_guard_fits_a_word() -> None:
    _check('let f = (n:int64):>int64 => {\n    i = 0\n    loop i <? n { i += 1 }\n    return i\n}')


def test_a_counter_that_can_pass_the_word_is_still_rejected() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits `int64`'):
        _check('let f = (n:int64):>int64 => {\n    i = 0\n    loop true { i += 1  if i >? n break }\n    return i\n}')


def test_a_let_field_constructs_through_a_type_prefix() -> None:
    # `Protocol[let eat = …]` means the same as `Protocol[eat = …]`, as the untyped literal already did
    _check('let P:type = [eat:<(n:int64):>int64> extra:int64=0]\nlet w = P[let eat = (n:int64):>int64 => n + 1]\nlet r:int64 = w.eat(1) + w.extra')


def test_else_inside_match_braces_is_a_diagnostic() -> None:
    with pytest.raises(ReportException, match='`else` is not a match arm'):
        _check('let f = (n:int64):>int64 => match n { m:4 => 1  else => 2 }')
