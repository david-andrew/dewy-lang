"""Finalizing, resetting, deferred bodies, scope exits and parallel range proofs agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'parallel_range_bound/zero_start',
    'ownership/fixed_move_only',
    'exact_int/midpoint',
    'match/union_guard_facts',
    'parallel_range_bound/unproven_rejected',
    'ownership/growable_replacement_boundary',
    'ownership/scalar_uninitialized',
]


def test_facts_lifecycle_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
