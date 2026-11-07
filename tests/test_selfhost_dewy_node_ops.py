"""Reader node builders (value names, text, ranges, singletons, test functions, reserved names, targets)
agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'default_proofs/refuted_literal_union',
    'loop/else_iterators',
    'dogfood/18_roman_tests',
    'frontend/m_directives_direct_directives_identity_1',
    'constant/shadowable_import',
    'end/reserved_assignment',
    'frontend/declarations_declaration_fallback_1',
]


def test_dewy_node_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
