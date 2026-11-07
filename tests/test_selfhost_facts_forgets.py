"""Forgetting exposed roots, call effects, text sinks and routed writes agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'fixed/array_update_parameters',
    'checked_index/store',
    'compound/custom_width',
    'place_method/try_lock',
    'checked_index/later_argument',
    'witness/nonempty_relation_headline',
    'dogfood30_proofs/dict_helper_rejected',
]


def test_facts_forgets_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0


# (with this leaf alone switched: the summary leaf has moved on from its frozen twin)
def test_facts_forgets_record_lengths(compiler, tmp_path, monkeypatch):
    cases = ['record_length_summary/accepted', 'record_length_summary/grows', 'record_length_summary/other_field']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=('facts_forgets',)) > 0
