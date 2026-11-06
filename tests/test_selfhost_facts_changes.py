"""Change effects of bodies on facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'misc/zero_divisor_remainder_uint64',
    'range/unit_exhausted_1',
    'generic/value_result',
    'units/containers',
    'facts/partial_keeps_facts',
    'dogfood17_proofs/pop_insert_length',
]


def test_facts_changes_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
