"""Explanations of unproven obligations agree with frozen Jo, text for text."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'place_method/early_exits',
    'facts/receiver_selector_once',
    'set/string_set_intersection_local',
    'ownership/growable_move_only',
    'tensor/shaped_mismatch',
    'units/containers',
    'witness/projection_call_returned_branch',
    'witness/proof_exit',
    'witness/conjunct_refuted',
    'slice/unproven',
    'uint64_ceiling/result_reject',
    'notraps18_bytes/interior_char',
    'argument/local_place_deep',
    'proof_help/projected_bound_named',
    'proof_help/script_int_width',
]


def test_witness_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
