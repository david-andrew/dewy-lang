"""Check exact mixed-sign comparisons: reads compared in place, other operands held once, in order."""

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_mixed_sign_compare_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, "mixed_sign_compare", (
        "mixed_sign_compare/all_operators", "mixed_sign_compare/fields_and_widths",
        "mixed_sign_compare/call_operand",
    ))
