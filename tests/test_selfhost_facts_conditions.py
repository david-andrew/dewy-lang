"""Condition facts and implications agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'match/union_guard_facts',
    'channels/optional_receive_narrowing',
    'dogfood28_proofs/match_in_loop_keeps_length',
]


def test_facts_conditions_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
