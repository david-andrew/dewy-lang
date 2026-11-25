"""Field narrowing diagnostics agree with frozen witness_ops."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_witness_ops_narrowing_field(compiler, tmp_path, monkeypatch):
    cases = ['census_proofs/narrowing_field_named', 'census_proofs/narrowing_field_proven']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('witness_ops',)) == 1
