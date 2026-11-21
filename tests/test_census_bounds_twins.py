"""Check the facts_changes loop transfer and its frozen twin on the same programs."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_loop_call_lengths(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/loop_calls', 'census_bounds/loop_call_may_shrink']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 1


def test_facts_pushes_keeps_entry_bound(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/counted_pushes', 'census_bounds/conditional_pushes',
             'census_bounds/push_in_selector', 'census_bounds/push_replaced_in_rhs',
             'census_bounds/conditional_push_replaces_element']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 2
