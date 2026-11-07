"""Cold refinement helpers (dictionary keys, string sets, self-length arrays, lengths, results) agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'self_length/runtime_shrink_fails',
    'dictionary/totaldict',
    'refinement_aggregates/construct',
    'refinements/generic',
    'refine_union_storage/union_payload_text_isnt_ok',
    'record_field_shape/free_dimension',
    'self_length/no_pop_index',
    'dictionary/totaldict_pop',
    'length_in_place/generic_needs_guard',
]


def test_refine_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
