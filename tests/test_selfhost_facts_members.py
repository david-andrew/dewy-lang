"""Shared analysis of admitted member copies agrees with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = ['record/inline_map', 'tests/ladder/99_dewy_frontend/design.dewy']


def test_facts_members_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
