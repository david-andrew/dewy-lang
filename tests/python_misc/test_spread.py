"""Spreading `x...` into object and array literals."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def _object_fields(declared: dict[str, hir.Declare], name: str) -> list[str]:
    return [field.name for field in declared[name].expr.type.fields]


def test_object_spread_copies_fields_in_order_and_later_wins() -> None:
    declared = _declared("let a = [x=1 y=2]\nlet b = [z=3]\nlet c = [a... w=0 b...]\nlet d = [a... x=9]\nlet e = [a... [y=5 x=6]... ]\n".replace("[y=5 x=6]...", "f...").replace("let e =", "let f = [y=5 x=6]\nlet e ="))
    assert _object_fields(declared, 'c') == ['x', 'y', 'w', 'z']
    assert _object_fields(declared, 'd') == ['x', 'y']
    assert _object_fields(declared, 'e') == ['x', 'y']  # order from first occurrence, values from the later spread


def test_two_written_fields_with_one_name_are_still_a_mistake() -> None:
    with pytest.raises(UserError, match='duplicate object field'):
        _declared("let a = [x=1]\nlet b = [a... y=1 y=2]\n")


def test_array_spread_lengths_add_up_or_go_runtime() -> None:
    declared = _declared("let xs:array<int64 length=2> = [1 2]\nlet fixed = [xs... 0 xs...]\nlet grow = (ys:array<int64>):>array<int64> => [ys... 1]\n")
    assert declared['fixed'].expr.type == ty.ArrayType('int64', 5)
    assert any(isinstance(item, hir.Spread) for item in declared['fixed'].expr.items)
    body = declared['grow'].expr.body
    literal = body.items[0] if isinstance(body, hir.Block) else body
    assert literal.type == ty.ArrayType('int64', None)  # a parameter's length is not known


def test_spread_operands_must_fit_the_literal() -> None:
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared("let xs:array<string> = [\"a\"]\nlet bad = [xs... 1]\n")  # `1` is not a string
    with pytest.raises(TypeCheckError, match='array elements are not homogeneous'):
        _declared("let xs:array<string> = [\"a\"]\nlet ns:array<int64> = [1]\nlet bad = [xs... ns...]\n")
    with pytest.raises(UserError, match='array spread requires an array or set'):
        _declared("let o = [a=1]\nlet bad = [o... 1]\n")
    with pytest.raises(UserError, match='object spread requires an object'):
        _declared("let xs:array<int64> = [1]\nlet bad = [xs... a=1]\n")
    with pytest.raises(UserError, match='cannot spread a union-typed value'):
        _declared("let f = (v:[a:int64]|none):>[a:int64] => [v...]\n")
    with pytest.raises(NotImplementedYet, match='spreading a computed value'):
        _declared("let mk = ():>[a:int64] => [a=1]\nlet bad = [mk()... b=2]\n")


def test_dictionary_and_set_literal_spreads_are_deferred() -> None:
    with pytest.raises(NotImplementedYet, match='dictionary literal'):
        _declared("let d = [\"k\" -> 1]\nlet e = [d... \"j\" -> 2]\n")
    with pytest.raises(NotImplementedYet, match='set literal'):
        _declared("let s = set[1]\nlet t = set[s... 2]\n")
