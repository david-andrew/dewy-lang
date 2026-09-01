"""Declared `never` results: divergence is checked, propagated, and narrowing."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError

PANIC = "let panic = (msg:string?=none):>never => {\n    if msg isnt? none printl(msg)\n    exit(1)\n}\n"


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_a_never_function_must_diverge() -> None:
    _check(PANIC)
    with pytest.raises(TypeCheckError, match='expected `never`, got `void`'):
        _check("let lied = ():>never => {\n    printl('back soon')\n}")


def test_a_call_to_a_never_function_is_bottom_and_narrows() -> None:
    root = _check(PANIC + 'classify = (v:int64?):>int64 => {\n    if v is? none panic("no value")\n    return v * 2\n}')
    classify = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'classify')
    assert classify.expr.rettype == 'int64'   # type: ignore[union-attr]   # `v * 2` checked with `v` narrowed


def test_a_diverging_arm_contributes_no_type() -> None:
    root = _check(PANIC + 'let x:int64 = if 1 <? 2 21 else panic("impossible")')
    declare = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'x')
    assert ty.strip_refinement(declare.annotation) == 'int64'
