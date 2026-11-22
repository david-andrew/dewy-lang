"""Check stored node types through literal, inferred and rewritten expressions."""

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


def test_expression_types_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    compare_golden_cases(compiler, tmp_path, monkeypatch, "expression_types", (
        "generic/array_literal_deferred_float", "singleton/membership_text_needle",
        "census_proofs/narrowing_field_named", "conversion/int_boundary_diagnostic",
    ))
