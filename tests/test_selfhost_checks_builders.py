"""Syntax tree builders agree with frozen Jo."""
from tests.selfhost_checks_double import compare_checks
from tests.support import compiler  # noqa: F401

CASES = [
    'frontend/m_tasks_migrated_tasks_diagnostics_7',
    'misc/main_float_result',
    'frontend/flows_flow_fallback_diagnostics_3',
    'precision_inference/key_outside',
    'numeric/broadcast_matrix_selection_constant',
    'ownership/growable_dictionary_move_only',
    'set/spread_wrong_type',
    'dictionary/counted_keys',
    'arena/reject_return',
    'frontend/strings_string_diagnostics_4',
    'numeric/broadcast_selection_mask_constant',
]


def test_checks_builders_twins(compiler, tmp_path, monkeypatch):
    compiled, rejected = compare_checks(compiler, tmp_path, monkeypatch, CASES)
    assert compiled + rejected == len(CASES)
