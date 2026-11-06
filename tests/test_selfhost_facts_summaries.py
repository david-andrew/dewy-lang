"""Return summaries and constructor joins agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'facts/returned_tuple_extreme',
    'unpack/loop_nested_sequence',
    'copies/strict_copy_fresh_replacement',
    'refinements/alias_conversion',
    'nd_contracts/mutable_entry',
    'facts/returned_tuple_arrays',
]


def test_facts_summaries_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
