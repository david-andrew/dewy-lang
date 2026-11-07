"""Type test services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'refine_alias_tags/element_nested_field',
    'optional/union_else_narrowing_path_write',
    'match/union_guard_facts',
    'dogfood30_proofs/search_missing_hint',
    'errors/string_literal_match_hint',
    'match/void_union_trailing_family',
    'dogfood36_proofs/optional_union_foreign_member_rejected',
    'dogfood30_proofs/search_int_hint',
]


def test_checks_istype_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
