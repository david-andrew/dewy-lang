"""Fork seeds and call argument capture agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'sequence/minmax_by_no_tail_allocation',
    'frontend/m_statements_direct_statements_identity_1',
    'refinements/uint_zero',
    'dogfood20_proofs/chosen_element_wider',
    'dogfood19_proofs/key_callback_other',
]


def test_facts_forks_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
