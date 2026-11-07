"""Interval sums, products, relational bounds, prereads and selected rows agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'misc/unsigned_constant_math',
    'uint64_ceiling/saved_guard',
    'range/stepped_error_10',
    'facts/nonlinear',
    'uint64_ceiling/result_reject',
    'saved_operands/false_reject',
]


def test_facts_arith_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
