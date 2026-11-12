"""Physical quantity types, constants, arithmetic and display agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'units/functions',
    'units/sleep',
    'time_clock/waits_entry',
    'time_clock/ticker_entry',
    'units/format_shown_unit',
    'units/conversions',
    'no_deadlocks/certified_locks',
    'units/temperature_point_scaled',
    'units/mismatch_assign',
    'units/temperature_computed_added',
    'units/temperature_computed_compared',
    'units/rvalue_point_in_unit',
    'units/rvalue_point_factor',
    'default_proofs/unit_decimal_float_named',
    'units/trigonometry_dimension',
    'units/as_unit_dimension',
    'units/dimensioned_power',
    'units/mismatch_add',
    'units/nonnumeric',
    'units/runtime_power',
]


def test_unit_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
