"""Exact-counter progress recognition agrees with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = ['sequence/nested_field_paths', 'generic/pool_direct_impostor']


def test_facts_progress_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
