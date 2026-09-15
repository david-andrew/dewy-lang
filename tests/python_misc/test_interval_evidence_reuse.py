"""Reusing immutable bounds must not lose evidence or manufacture a fact sentinel."""
import pytest

from dewy.semantic.analyze.bounds import Interval, _ANY_FACT, _BoundsValidator, _word_range


@pytest.mark.parametrize('operation', ['union', 'intersect', 'widen'])
def test_equal_bounds_keep_cap_evidence_and_leave_operands_unchanged(operation):
    proven = Interval(0, 7)
    capped = Interval(0, 7, capped=True)
    # Interval equality deliberately ignores the evidence flag, so equality
    # alone is insufficient to choose which existing record can be reused.
    assert proven == capped
    for left, right in ((proven, capped), (capped, proven)):
        result = getattr(left, operation)(right)
        assert (result.lower, result.upper, result.capped) == (0, 7, True)
    assert not proven.capped
    assert capped.capped


@pytest.mark.parametrize('operation', ['union', 'intersect', 'widen'])
def test_interval_arithmetic_does_not_create_vacuous_fact_identity(operation):
    unknown = Interval(None, None)
    for left, right in ((unknown, _ANY_FACT), (_ANY_FACT, unknown), (_ANY_FACT, _ANY_FACT)):
        result = getattr(left, operation)(right)
        assert result is not _ANY_FACT
        assert (result.lower, result.upper, result.capped) == (None, None, False)


def test_extended_intervals_retain_plain_arithmetic_result():
    class ExtendedInterval(Interval):
        pass

    value = ExtendedInterval(1, 2)
    for operation in ('union', 'intersect', 'widen'):
        assert type(getattr(value, operation)(value)) is Interval


def test_numeric_range_queries_use_current_limit_width_and_signedness():
    validator = _BoundsValidator.__new__(_BoundsValidator)
    for limit in (1024, 255, 1024):
        validator.max_length = limit
        interval = validator._length_default()
        assert (interval.lower, interval.upper, interval.capped) == (0, limit, True)
    for width in (8, 16, 32, 64):
        signed = _word_range(width, True)
        unsigned = _word_range(width, False)
        assert (signed.lower, signed.upper, signed.capped) == (
            -(1 << (width - 1)), (1 << (width - 1)) - 1, False)
        assert (unsigned.lower, unsigned.upper, unsigned.capped) == (0, (1 << width) - 1, False)
