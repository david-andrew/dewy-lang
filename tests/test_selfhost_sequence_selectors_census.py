"""User-facing mask-length contracts agree with frozen sequence_selectors."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_sequence_selectors_mask_guard(compiler, tmp_path, monkeypatch):
    cases = ['census_proofs/mask_guard_named', 'census_proofs/mask_guard_proven']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('sequence_selectors',)) == 1
