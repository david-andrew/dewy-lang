"""Checker-level coverage for the 2026-09-01 bootstrap-gap fixes and diagnostics."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_double_equals_names_the_real_operator() -> None:
    with pytest.raises(UserError, match='`==` is not an operator') as info:
        _check('let main = ():>int64 => {\n    let x = 1\n    if x == 1 { return 1 }\n    return 0\n}')
    assert 'equality is `=?`' in str(info.value.report)


def test_colon_result_type_hints_the_arrow() -> None:
    with pytest.raises(UserError, match='result type is written `:>`'):
        _check('main = (argv:array<string>):int64 => {\n    return 0\n}')


def test_optional_returning_main_is_an_error_not_a_crash() -> None:
    with pytest.raises(UserError, match='`main` must return an integer or `void`'):
        _check('let main = (argv:array<string>):>uint64? => {\n    return none\n}')


def test_unproven_index_blames_the_unknown_length() -> None:
    with pytest.raises(UserError, match='array index is not proven') as info:
        _check('let main = (argv:array<string>):>int64 => {\n    printl(argv[0])\n    return 0\n}')
    report = str(info.value.report)
    assert 'nothing establishes the array' in report and 'guard on the length first' in report


def test_mixed_width_comparison_casts_the_right_operand_with_a_proof() -> None:
    _check('let f = (i:uint64 s:string):>bool => i <? s.length')
    with pytest.raises(UserError, match='cannot prove this integer fits `uint8`'):
        _check('let f = (i:uint8 w:int64):>bool => i <? w')   # the proof still gates it


def test_nested_unpacking_names_every_field() -> None:
    _check("let d:dict<string [a:int64 b:int64]> = ['x' -> [a=1 b=2]]\nlet main = ():>int64 => {\n    let t:int64 = 0\n    loop [k [a b]] in d { t += a + b }\n    return t\n}")
    with pytest.raises(UserError, match='must name every field'):
        _check("let d:dict<string [a:int64 b:int64]> = ['x' -> [a=1 b=2]]\nlet main = ():>int64 => {\n    loop [k [a]] in d { }\n    return 0\n}")


def test_intersection_strengthens_but_never_weakens() -> None:
    root = _check("Context:type = [depth:int64]\nRoot = Context & [tag:string='root']\nlet r = Root(depth=1)")
    declare = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'r')
    assert [field.name for field in declare.expr.type.fields] == ['depth', 'tag']   # type: ignore[union-attr]
    with pytest.raises(TypeCheckError, match='weakens'):
        _check("A:type = [x:int8]\nB = A & [x:int64]\nlet b = B(x=1)")


def test_minted_override_keeps_the_subtype_rule() -> None:
    _check("let Report = type of any & [severity='none']\nlet Err = type of Report & [severity='error']")
    with pytest.raises(UserError, match='weakens field'):
        _check("let A = type of any & [x:int8]\nlet B = type of A & [x:int64]")
