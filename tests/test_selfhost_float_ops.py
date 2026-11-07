"""Float conversion guards, dictionary key proofs and the no-NaN and no-infinity analysis agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'float_guards/field_guard',
    'dictionary/float_key_proven',
    'comptime/semantics',
    'conversion/float_limits',
    'float_guards/library_tests',
    'dictionary/float_key_nan_literal',
    'directives/no_inf_incoming_runtime',
    'directives/no_nan_proven',
    'directives/no_inf_runtime',
    'notraps11/integer_float',
    'notraps11/integer_float_bounds',
    'notraps11/integer_float_reject',
    'notraps11/integer_float_write_reject',
    'float_guards/field_reassigned',
    'directives/no_inf_divisor',
    'directives/no_nan_parsed_key',
    'directives/no_nan_entering',
    'directives/no_inf_caller',
    'float_constants/reject_inf_in_scope',
]


def test_float_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
