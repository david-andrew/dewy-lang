"""Decimal bindings that start a body over agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'import_cycles/use_before_init_one_file',
    'juxtaposition/spaced_unit',
    'optimizer/record_return_loop',
    'decimal/global_writers',
    'comptime/mutable_global',
    'decimal/adapts_to_float',
    'decimal/lambda_bindings',
    'decimal/script_accumulator',
    'decimal/generic_accumulator',
    'decimal/float_after_read',
]


def test_decimal_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
