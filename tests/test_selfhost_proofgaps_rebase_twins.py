"""Proofgaps collection certificates agree after combining the twin changes."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_proofgaps_rebased_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'proofgaps/callee_replace',
        'proofgaps/dictionary_clear',
        'proofgaps/dictionary_empty',
        'proofgaps/dictionary_not_distinct',
        'proofgaps/field_dictionary',
        'proofgaps/counted_callback',
        'proofgaps/counted_filtered',
        'proofgaps/counted_shortened',
        'proofgaps/sort_capture_push',
        'proofgaps/sort_key_parameter',
        'proofgaps/sort_key_writes_global',
        'proofgaps/sort_named_key_writes_global',
        'proofgaps/sort_then_clear',
        'record_length_summary/grows',
    ]) > 0
