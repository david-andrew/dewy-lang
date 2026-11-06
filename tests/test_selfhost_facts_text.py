"""String, byte and search facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'spread/call_context',
    'notraps18_bytes/slice',
    'facts/narrowed_join_bound',
    'dogfood34_proofs/optional_text',
    'dogfood22_proofs/text_helper_keeps_roots',
    'ownership/growable_move_only',
    'library_preconditions/find_start_unproven',
    'byte_slice/unproven_boundary',
    'dogfood18_proofs/conditional_push_or_pop',
    'library_preconditions/find_start_refuted',
    'notraps12/pop_empty_reject',
]


def test_facts_text_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
