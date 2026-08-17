import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, UserError
from dewy.semantic.hir_display import hir_to_dewy


def _check(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _iterator(range_source: str) -> hir.IteratorExpression:
    root = _check(f'loop i in {range_source} {{}}')
    flow = root.items[0]
    assert isinstance(flow, hir.Flow)
    iterator = flow.arms[0].condition
    assert isinstance(iterator, hir.IteratorExpression)
    return iterator


@pytest.mark.parametrize(
    ('source', 'first', 'step', 'last', 'count'),
    [
        ('0,2..10', 0, 2, 10, 6),
        ('5,3..0', 5, -2, 1, 3),
        ('(0,2..10]', 2, 2, 10, 5),
        ('[0,2..10)', 0, 2, 8, 5),
        ('(10,8..0)', 8, -2, 2, 4),
        ('2,4..1', 2, 2, 0, 0),
    ],
)
def test_finite_stepped_range_normalization(
    source: str,
    first: int,
    step: int,
    last: int,
    count: int,
) -> None:
    iterator = _iterator(source)
    assert (
        iterator.first,
        iterator.step,
        iterator.last,
        iterator.count,
    ) == (first, step, last, count)
    assert iterator.target.type == 'int64'


def test_step_pair_hir_and_display_preserve_surface_shape() -> None:
    root = _check('let values = 0,2..10 let tail = ..8,10')
    values = root.items[0]
    tail = root.items[1]
    assert isinstance(values, hir.Declare)
    assert isinstance(values.expr, hir.Range)
    assert values.expr.step_pair is not None
    assert hir_to_dewy(values.expr) == '0,2..10'
    assert isinstance(tail, hir.Declare)
    assert isinstance(tail.expr, hir.Range)
    assert hir_to_dewy(tail.expr) == '..8,10'


def test_static_expressions_can_supply_range_anchors() -> None:
    root = _check("""
const first:int64 = 1
const second:int64 = first + 2
loop i in first,second..10 {}
""")
    flow = root.items[2]
    assert isinstance(flow, hir.Flow)
    iterator = flow.arms[0].condition
    assert isinstance(iterator, hir.IteratorExpression)
    assert (iterator.first, iterator.step, iterator.last, iterator.count) == (
        1,
        2,
        9,
        5,
    )


def test_right_unbounded_ranges_have_bigint_targets() -> None:
    ascending = _iterator('0..')
    descending = _iterator('5,3..')
    assert (
        ascending.first,
        ascending.step,
        ascending.last,
        ascending.count,
        ascending.target.type,
    ) == (0, 1, None, None, 'int')
    assert (
        descending.first,
        descending.step,
        descending.last,
        descending.count,
        descending.target.type,
    ) == (5, -2, None, None, 'int')


@pytest.mark.parametrize('source', ['..10', '..8,10', '..'])
def test_left_unbounded_ranges_cannot_be_iterated(source: str) -> None:
    with pytest.raises(UserError, match='requires a left anchor'):
        _iterator(source)


@pytest.mark.parametrize('source', ['1,1..10', '1,1..'])
def test_zero_step_range_iteration_is_rejected(source: str) -> None:
    with pytest.raises(UserError, match='step cannot be zero'):
        _iterator(source)


def test_invalid_trailing_step_pair_is_rejected() -> None:
    with pytest.raises(UserError, match='trailing range step pairs'):
        _check('let values = 0..8,10')


def test_nonconstant_iterator_anchor_is_rejected() -> None:
    with pytest.raises(UserError, match='compile-time integers'):
        _check("""
let f = (stop:int64):>void => {
    loop i in 0,2..stop {}
}
""")


@pytest.mark.parametrize(
    ('operator', 'finite_optional', 'repeats'),
    [
        ('and', False, False),
        ('or', True, True),
        ('xor', False, False),
        ('nand', False, False),
        ('nor', False, False),
        ('xnor', False, False),
    ],
)
def test_unbounded_multiiterator_truth_analysis(
    operator: str,
    finite_optional: bool,
    repeats: bool,
) -> None:
    root = _check(f'loop infinite in 0.. {operator} finite in 0..1 {{}}')
    flow = root.items[0]
    assert isinstance(flow, hir.Flow)
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.MultiIteratorExpression)
    infinite, finite = condition.iterators
    assert infinite.count is None
    assert infinite.target.type == 'int'
    assert (ty.optional_payload(finite.target.type) is not None) == finite_optional
    assert condition.repeats_when_exhausted == repeats


def test_unbounded_bounds_can_be_narrowed_for_array_indexing() -> None:
    _check("""
let sum = ():>int64 => {
    let values:array<int64> = [10 20 12]
    let total:int64 = 0
    loop i in 0.. {
        if i <? values.length {
            total += values[i]
        } else {
            break
        }
    }
    return total
}
""")


def test_descending_range_bounds_prove_sparse_indices() -> None:
    _check("""
let sum = ():>int64 => {
    let values:array<int64> = [1 2 3 4 5 6]
    let total:int64 = 0
    loop i in 5,3..0 {
        total += values[i]
    }
    return total
}
""")


def test_stepped_range_codegen_uses_scaled_offset() -> None:
    emitted = codegen(SrcFile(None, """
let f = ():>int64 => {
    let total:int64 = 0
    loop i in 5,3..0 {
        total += i
        continue
    }
    return total
}
"""))
    assert '__dewy_iterator_value_1 = 5 + (__dewy_iterator_1 * -2)' in emitted
    assert emitted.count('__dewy_iterator_1 += 1') == 1


def test_unbounded_udewy_lowering_requires_bigint() -> None:
    with pytest.raises(
        NotImplementedYet,
        match='unbounded range iteration requires bigint lowering',
    ):
        codegen(SrcFile(None, 'loop i in 0.. {}'))


def test_finite_bigint_range_is_semantic_but_not_udewy_lowerable() -> None:
    source = 'loop i in 9223372036854775808..9223372036854775809 {}'
    iterator = _iterator('9223372036854775808..9223372036854775809')
    assert iterator.target.type == 'int'
    with pytest.raises(
        NotImplementedYet,
        match='range iteration requires bigint lowering',
    ):
        codegen(SrcFile(None, source))
