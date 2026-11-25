"""Unsigned comparisons keep zero reachable across conditional expressions."""
from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_exact_fact_transfer_unsigned_zero(compiler, tmp_path, monkeypatch):
    cases = [f'unsigned_zero/{name}' for name in ('call_arm', 'arm_order', 'positive_arms', 'unequal')]
    compare_golden_cases(compiler, tmp_path, monkeypatch, 'exact_fact_transfer', cases)
