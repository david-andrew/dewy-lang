"""Index and receiver services agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'refine_alias_tags/element_nested_field',
    'frontend/strings_string_diagnostics_4',
    'comptime/reject_string_index',
    'fixed/array_selections',
    'dogfood33_proofs/dict_fallback_rejected',
    'frontend/direct_direct_expression_diagnostics_4',
    'dictionary/keys_set_index',
    'witness/pool_entry_copy',
    'numeric/broadcast_selection_constant',
    'range/index_stepped_string',
]


def test_checks_index_hooks_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
