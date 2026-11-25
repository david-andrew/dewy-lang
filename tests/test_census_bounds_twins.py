"""Check the facts_changes loop transfer and its frozen twin on the same programs."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_loop_call_lengths(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/loop_calls', 'census_bounds/loop_call_may_shrink']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 1


def test_facts_pushes_keeps_entry_bound(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/counted_pushes', 'census_bounds/conditional_pushes',
             'census_bounds/push_in_selector', 'census_bounds/push_replaced_in_rhs',
             'census_bounds/conditional_push_replaces_element']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 2


def test_loop_sort_lengths(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/loop_sort', 'census_bounds/loop_sort_callback_shrinks']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 1


def test_global_write_summaries(compiler, tmp_path, monkeypatch):
    # facts_forgets requests the facts_summaries transfer. facts_capture
    # visits all exits, including absent optional results.
    cases = ['census_bounds/global_helpers', 'census_bounds/global_optional_shrink',
             'census_bounds/global_grow_is_not_exact']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 1


def test_optional_place_summaries(compiler, tmp_path, monkeypatch):
    cases = ['census_bounds/optional_helper_grows', 'census_bounds/optional_helper_shrinks']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) == 1
