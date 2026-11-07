"""Routes, reads, stored patterns and constant globals agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'comptime/storage',
    'unpack/top_level_updates',
    'refinement_aggregates/swap_elements',
    'dogfood30_proofs/dict_helper_rejected',
    'dogfood20_proofs/pattern_swap_unguarded',
    'census_proofs/equality_element_hook',
    'self_length/bound_forms',
    'self_length/build_with_push_loop',
]


def test_facts_routes_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
