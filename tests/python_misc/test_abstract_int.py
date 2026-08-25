import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError
from dewy.backend.udewy import codegen


def _check(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_abstract_int_meets_fixed_widths_at_the_fixed_width() -> None:
    declared = _check('let a = 5\nlet b:int64 = 7 transmute int64\nlet c = a + b\nlet d:int64 = a * 3')
    assert declared['c'].expr.type == 'int64'
    assert isinstance(declared['d'].expr, hir.ValueCast) and declared['d'].expr.type == 'int64'


def test_proven_abstract_int_arithmetic_lowers_to_words() -> None:
    emitted = codegen(SrcFile(None, 'let a = 5\nlet b = a * 3 + 1\nlet main = ():>int64 => { printl"{b}" return b }'))
    assert '(a * 3) + 1' in emitted


def test_unbounded_abstract_int_arithmetic_is_rejected() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits `int64`'):
        codegen(SrcFile(None, 'let grow = (n:int):>int => n * 2\nlet main = ():>int64 => { let g:int64 = grow(3) return g }'))


def test_narrowing_an_unproven_int_is_rejected() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits `int64`'):
        codegen(SrcFile(None, 'let f = (n:int):>int64 => n\nlet main = ():>int64 => f(3)'))


def test_loop_accumulation_without_a_bound_is_rejected() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits'):
        codegen(SrcFile(None, 'let main = ():>int64 => {\n    let total = 0\n    let step = 3\n    loop i in 0..10 { total = total + step }\n    return total\n}'))
