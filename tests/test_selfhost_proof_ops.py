"""Proof terms, erasure, result contracts and their evidence agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'facts/pool_calls_effects',
    'witness/proof_exit',
    'witness/int_counter_result',
]


def test_proof_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
