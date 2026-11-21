"""Fixed-width arithmetic repair spellings agree with frozen exact_fact_transfer."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_exact_fact_transfer_overflow_type_repair(compiler, tmp_path, monkeypatch):
    cases = ['census_proofs/overflow_type_named', 'census_proofs/overflow_type_proven']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('exact_fact_transfer',)) == 1
