"""Literals in type positions denote singleton types."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_literal_annotations_are_singleton_types() -> None:
    declared = _declared('let a:5 = 5\nlet s:"one" = "one"\nlet b:0x"6869" = 0x"6869"\n')
    assert declared['a'].annotation == ty.IntegerLiteralType(5)
    assert declared['s'].annotation == ty.StringLiteralType('one')
    assert declared['b'].annotation == ty.BinaryLiteralType(b'hi')


def test_literal_unions_and_type_blocks() -> None:
    declared = _declared('let Mode:type = <1 | 2 | "fast">\nlet f = (m:Mode):>int64 => if m is? "fast" 1 else 0\nlet g = (v:1|2):>int64 => 0\n')
    mode = declared['Mode'].expr.value
    assert isinstance(mode, ty.TypeOr) and ty.StringLiteralType('fast') in mode.items and ty.IntegerLiteralType(1) in mode.items
    # a union of integer singletons at a value boundary is a word with its value set as invariant
    assert declared['g'].expr.type.pos_or_kw[0].type == ty.RefinedType('int64', (ty.Proposition('self', '>=?', 1), ty.Proposition('self', '<=?', 2)))


def test_literal_parameters_specialize_overloads() -> None:
    declared = _declared("""
let DivZero:type = type of error
let safe_div = ((n:int64 d:0):>DivZero => DivZero) & ((n:int64 d:int64 & ~0):>int64 => n // d)
let main = ():>int64 => { let a = safe_div(6 0) let b = safe_div(6 3) return 0 }
""")
    body = declared['main'].expr.body
    calls = [item.expr for item in body.items if isinstance(item, hir.Declare)]
    assert [call.selected_method_index for call in calls] == [0, 1]
    # each call has the selected method's own result type, not a union of all methods'
    assert [str(call.type) for call in calls] == ['DivZero', 'int64']


def test_literal_mismatches_and_unsupported_forms() -> None:
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared('let s:"one" = "two"\n')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared('let n:5 = 6\n')
    with pytest.raises(NotImplementedYet, match='boolean literal type'):
        _declared('let t:true = true\n')


def test_singleton_union_words_reject_other_values() -> None:
    _declared('let s:-1|1 = 1\nlet t:-1|1 = -1\n')
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let s:-1|1 = 0\n')
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let f = (s:-1|1):>-1|1 => 2\n')
