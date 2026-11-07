"""Comparison and variant hints agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'units/parameter_mismatch',
    'coalesce/array_binding_nested',
    'array/comparison_different_arrays',
    'surface/bare_none_type',
    'surface/union_operand_failure',
    'float_constants/reject_old_inf',
    'units/generic_mismatch',
    'coalesce/array_binding_fallback',
    'surface/compare_union_number',
    'x:int|none=none\nif x <? 3 {printl(1)}\n',
]


def test_checks_compare_hints_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
