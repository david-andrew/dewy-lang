"""A comparison between two terms is kept as a fact about their difference."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError


def _check(source: str) -> None:
    check.typecheck_and_resolve(SrcFile(None, source))


def test_a_length_minus_a_guarded_index_is_positive() -> None:
    _check(
        'let f = (src:string):>uint64 => {\n    i:int64 = 0\n    loop i <? src.length {\n'
        '        let rest:uint64 = src.length - i\n        return rest\n    }\n    return 0\n}'
    )


def test_a_span_width_is_nonnegative_between_ordered_positions() -> None:
    _check('let f = (a:int64 b:int64):>uint64 => {\n    if 0 <=? a <=? b { let w:uint64 = b - a return w }\n    return 0\n}')
    _check('let f = (a:int64 b:int64):>uint64 => {\n    if a =? b { let w:uint64 = b - a return w }\n    return 0\n}')


def test_an_unordered_difference_is_still_unproven() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits `uint64`'):
        _check('let f = (a:int64 b:int64):>uint64 => {\n    if 0 <=? a and 0 <=? b { let w:uint64 = b - a return w }\n    return 0\n}')


def test_the_fact_drops_when_a_term_is_assigned() -> None:
    with pytest.raises(UserError, match='cannot prove this integer fits `uint64`'):
        _check(
            'let f = (src:string):>uint64 => {\n    i:int64 = 0\n    total:uint64 = 0\n    loop i <? src.length {\n'
            '        i += 1\n        let rest:uint64 = src.length - i\n        total += rest\n    }\n    return total\n}'
        )
    with pytest.raises(UserError, match='cannot prove this integer fits `uint64`'):
        _check('let f = (a:int64 b:int64):>uint64 => {\n    if 0 <=? a <=? b { a = b + 1 }\n    let w:uint64 = b - a\n    return w\n}')


def test_the_fact_drops_when_the_sequence_shrinks_or_at_a_join() -> None:
    with pytest.raises(UserError, match='cannot prove'):
        _check(
            'let f = (xs:array<int64> i:int64):>uint64 => {\n    if 0 <=? i <? xs.length {\n'
            '        let last = xs.pop\n        let rest:uint64 = xs.length - i\n        return rest\n    }\n    return 0\n}'
        )
    with pytest.raises(UserError, match='cannot prove this integer fits `uint64`'):
        _check('let f = (a:int64 b:int64 c:bool):>uint64 => {\n    if c { if not (0 <=? a <=? b) return 0 }\n    let w:uint64 = b - a\n    return w\n}')


def test_fixed_width_arithmetic_keeps_its_width_under_an_expected_width() -> None:
    # `let w:uint64 = end - start` dispatches `int64 - int64`, then meets `uint64`
    _check('let f = (a:int64 b:int64):>uint64 => {\n    if 0 <=? a <=? b { let w:uint64 = b - a return w }\n    return 0\n}')
    _check('let f = (a:uint8 b:uint8):>int64 => {\n    let w:int64 = a + b\n    return w\n}')


def test_a_slice_length_is_its_endpoints_difference() -> None:
    nonempty = 'let f = (s:string<length >? 0>):>int64 => s.length\n'
    _check(nonempty + 'let g = (src:string):>int64 => {\n    i:int64 = 0\n    total:int64 = 0\n    loop i <? src.length { total += f(src[i..]) + f(src[i..end])  i += 1 }\n    return total\n}')
    _check(nonempty + 'let g = (src:string i:int64):>int64 => if 0 <? i <=? src.length f(src[0..i)) else 0')
    with pytest.raises(UserError, match='cannot prove refinement'):
        _check(nonempty + 'let g = (src:string i:int64):>int64 => if 0 <=? i <? src.length f(src[0..i)) else 0')   # `[0..0)` is empty
