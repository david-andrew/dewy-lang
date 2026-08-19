from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, UserError
from dewy.semantic.hir_display import hir_to_dewy
from udewy.frontend import entry_point


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


@pytest.mark.parametrize(
    ('expression', 'expected'),
    [
        ('16 in? (5..15]', False),
        ('15 in? (5..15]', True),
        ('5 in? (5..15]', False),
        ('8 in? 0,2..10', True),
        ('9 in? 0,2..10', False),
        ('100 in? ..', True),
        ('10 in? [..10)', False),
    ],
)
def test_exact_integer_range_membership_is_folded(
    expression: str,
    expected: bool,
) -> None:
    root = _check(f'let result = {expression}')
    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.Bool)
    assert declaration.expr.value is expected


def test_exact_integer_range_membership_lowers() -> None:
    emitted = codegen(SrcFile(None, 'let result = 16 in? (5..15]'))
    assert 'let result:bool = false' in emitted


def test_runtime_unstepped_range_membership_is_preserved_in_hir() -> None:
    root = _check('''
let candidate:int64 = 7
let lower:int64 = 5
let upper:int64 = 10
let result = candidate in? [lower..upper)
''')
    result = root.items[3]
    assert isinstance(result, hir.Declare)
    assert isinstance(result.expr, hir.RangeMembership)


def test_runtime_range_membership_operands_are_evaluated_once() -> None:
    emitted = codegen(SrcFile(None, '''
let next_value = ():>int64 => 7
let next_lower = ():>int64 => 5
let next_upper = ():>int64 => 10
let result = next_value() in? [next_lower()..next_upper())
'''))

    assert emitted.count('= next_value()') == 1
    assert emitted.count('= next_lower()') == 1
    assert emitted.count('= next_upper()') == 1


def test_runtime_candidate_in_static_stepped_range_is_preserved_and_lowered() -> None:
    root = _check('''
let candidate:int64 = 8
let result = candidate in? 0,2..10
''')
    result = root.items[1]
    assert isinstance(result, hir.Declare)
    assert isinstance(result.expr, hir.RangeMembership)
    assert (
        result.expr.first,
        result.expr.step,
        result.expr.last,
        result.expr.count,
    ) == (0, 2, 10, 6)

    emitted = codegen(SrcFile(None, '''
let next_value = ():>int64 => 8
let result = next_value() in? 0,2..10
'''))
    assert emitted.count('= next_value()') == 1
    assert ' % 2' in emitted


@pytest.mark.skipif(
    which('as') is None or which('ld') is None,
    reason='as/ld not available',
)
def test_runtime_unstepped_range_membership_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = '''
let closed_open = (value:int64 lower:int64 upper:int64):>bool =>
    value in? [lower..upper)
let open_closed = (value:int64 lower:int64 upper:int64):>bool =>
    value in? (lower..upper]
let below = (value:int64 upper:int64):>bool => value in? [..upper)
let above = (value:int64 lower:int64):>bool => value in? (lower..]
let even = (value:int64):>bool => value in? 0,2..10
let open_even = (value:int64):>bool => value in? (0,2..10]
let descending = (value:int64):>bool => value in? 10,7..1
let unbounded_even = (value:int64):>bool => value in? 0,2..

let main = ():>int64 => {
    if closed_open(5 5 10)
        and closed_open(9 5 10)
        and not closed_open(10 5 10)
        and not closed_open(4 5 10)
        and open_closed(10 5 10)
        and not open_closed(5 5 10)
        and below(9 10)
        and not below(10 10)
        and above(6 5)
        and not above(5 5)
        and even(8)
        and not even(9)
        and open_even(2)
        and not open_even(0)
        and descending(7)
        and not descending(8)
        and unbounded_even(100)
        and not unbounded_even(101) {
        return 42
    }
    return 1
}
'''
    path = tmp_path / 'runtime_range_membership.udewy'
    path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(path, []) == 42


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
    ('operator', 'finite_optional', 'repeats', 'infinite_count'),
    [
        ('and', False, False, 2),
        ('or', True, True, None),
        ('xor', False, False, 0),
        ('nand', False, False, 0),
        ('nor', False, False, 0),
        ('xnor', False, False, 2),
    ],
)
def test_unbounded_multiiterator_truth_analysis(
    operator: str,
    finite_optional: bool,
    repeats: bool,
    infinite_count: int | None,
) -> None:
    root = _check(f'loop infinite in 0.. {operator} finite in 0..1 {{}}')
    flow = root.items[0]
    assert isinstance(flow, hir.Flow)
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.MultiIteratorExpression)
    infinite, finite = condition.iterators
    assert infinite.count == infinite_count
    assert infinite.target.type == ('int' if infinite_count is None else 'int64')
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
