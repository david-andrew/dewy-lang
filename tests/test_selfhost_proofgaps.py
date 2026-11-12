"""Length certificates and their rejection paths agree with the frozen leaves."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_proofgaps_twins(compiler, tmp_path, monkeypatch):
    cases = [
        'proofgaps/callee_loop_push', 'proofgaps/callee_loop_shrink',
        'proofgaps/callee_push', 'proofgaps/callee_shrink',
        'proofgaps/callee_branch_shrink', 'proofgaps/callee_push_not_equal',
        'proofgaps/field_dictionary', 'proofgaps/dictionary_duplicates',
        'proofgaps/dictionary_not_distinct', 'proofgaps/dictionary_empty',
        'proofgaps/sort_callback', 'proofgaps/counted_callback',
        'proofgaps/counted_filtered', 'proofgaps/counted_shortened',
    ]
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 6
