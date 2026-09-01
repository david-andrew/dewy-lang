"""Loop conditions mixing iterator clauses with Boolean predicates."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def _loop(root: hir.Block) -> hir.LoopArm:
    main = root.items[-1].expr.body   # type: ignore[union-attr]
    flow = next(item for item in main.items if isinstance(item, hir.Flow) and isinstance(item.arms[0], hir.LoopArm))
    return flow.arms[0]   # type: ignore[return-value]


def test_predicates_become_a_guard_that_breaks_and_refine_the_body() -> None:
    root = _check(
        'let main = ():>int64 => {\n'
        '    let src = "  ab"\n'
        '    let n:int64 = 0\n'
        '    loop i in 0.. and i <? src.length and src[i] =? " " { n += 1 }\n'   # `src[i]` needs the first predicate
        '    return n\n'
        '}'
    )
    loop = _loop(root)
    assert isinstance(loop.condition, hir.IteratorExpression)
    assert loop.condition.guarded   # `i <? src.length` bounds the `0..` counter to a word
    assert isinstance(loop.body, hir.Block)
    guard = loop.body.items[0]
    assert isinstance(guard, hir.Flow) and isinstance(guard.default, hir.Break)
    assert isinstance(guard.arms[0], hir.IfArm) and isinstance(guard.arms[0].body, hir.Void)


def test_multiiterators_keep_their_predicates_too() -> None:
    root = _check(
        'let main = ():>int64 => {\n'
        '    let total:int64 = 0\n'
        '    loop a in [1 2 3] and b in [10 20 30] and a + b <? 30 { total += a + b }\n'
        '    return total\n'
        '}'
    )
    assert isinstance(_loop(root).condition, hir.MultiIteratorExpression)


def test_a_predicate_may_not_use_the_target_before_it_is_proven() -> None:
    with pytest.raises(UserError):
        _check(
            'let main = ():>int64 => {\n'
            '    let src = "  ab"\n'
            '    loop i in 0.. and src[i] =? " " { }\n'   # no length proof for the index
            '    return 0\n'
            '}'
        )


def test_only_a_strict_word_sized_upper_bound_guards_the_counter() -> None:
    root = _check('let main = ():>int64 => {\n    let n:int64 = 3\n    loop i in 0.. and n >? i { }\n    return 0\n}')
    assert _loop(root).condition.guarded   # type: ignore[union-attr]   # mirrored: bounds
    # `<=?` could reach n + 1, so the counter stays unbounded and is rejected as today
    with pytest.raises(UserError, match='cannot prove this integer fits'):
        _check('let main = ():>int64 => {\n    let n:int64 = 3\n    loop j in 0.. and j <=? n { }\n    return 0\n}')
