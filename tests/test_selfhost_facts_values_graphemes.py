"""Demanded literal grapheme lengths agree with the frozen facts_values twin."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_facts_values_literal_graphemes(compiler, tmp_path, monkeypatch):
    cases = ['census_proofs/unicode_literal_end', 'census_proofs/unicode_literal_index_rejected']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('facts_values',)) == 1
