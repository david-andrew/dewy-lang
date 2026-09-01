"""Comparison chains and fixed-width bounds inside refinement blocks."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def _parameter_propositions(root: hir.Block, name: str) -> list[tuple[str, str, int]]:
    function = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == name).expr
    assert isinstance(function, hir.FunctionLiteral)
    refined = function.pos_or_kw_args[0].type
    assert isinstance(refined, ty.RefinedType)
    return [(p.subject, p.op, p.value) for p in refined.propositions]


def test_a_length_chain_is_two_propositions_with_min_max_bounds() -> None:
    root = _check('let f = (s:string<0 <? length <=? uint64.max>):>int64 => s.length')
    assert _parameter_propositions(root, 'f') == [('length', '>?', 0), ('length', '<=?', (1 << 64) - 1)]


def test_a_lambda_chain_and_a_named_alias_work_too() -> None:
    root = _check(
        'nonempty = string<0 <? length <=? uint64.max>\n'
        'let g = (s:nonempty):>int64 => s.length\n'
        'let h = (x:int64<i => uint8.min <=? i <=? uint8.max>):>int64 => x'
    )
    assert _parameter_propositions(root, 'g') == [('length', '>?', 0), ('length', '<=?', (1 << 64) - 1)]
    assert _parameter_propositions(root, 'h') == [('self', '>=?', 0), ('self', '<=?', 255)]


def test_a_refinement_chain_reads_one_way() -> None:
    with pytest.raises(UserError, match='changes direction'):
        _check('let f = (x:int64<i => 0 <? i >? 10>):>int64 => x')


def test_the_chain_is_proven_and_refuted_like_separate_conditions() -> None:
    _check('let f = (s:string<0 <? length <=? uint64.max>):>int64 => s.length\nlet n = f("ab")')
    with pytest.raises(UserError, match='length >\\? 0'):
        _check('let f = (s:string<0 <? length <=? uint64.max>):>int64 => s.length\nlet n = f("")')
