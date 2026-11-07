"""Conditional services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'refine_alias_tags/element_nested_field',
    'surface/index_optional_member',
    'refine_alias_tags/sibling_branch',
    'target/runtime_test_checks_both_arms',
    'optional/is_chain_partial',
    'inference/then_branch_literal',
    'errors/condition_carried_exceptions',
    'object/recursive_literal_return',
    'search/regex_too_big',
]


def test_checks_cond_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
