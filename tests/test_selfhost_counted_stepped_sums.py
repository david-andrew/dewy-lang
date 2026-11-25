"""Stepped accumulation bounds match frozen facts_elements and facts_pushes."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_stepped_sums_match_twins(compiler, tmp_path, monkeypatch):
    cases = ['census_proofs/stepped_sum_bounds', 'census_proofs/stepped_sum_mutated_index']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases,
                         leaves=('facts_elements', 'facts_pushes')) == 1
