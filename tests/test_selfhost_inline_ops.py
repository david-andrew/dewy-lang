"""Inlining policy and its branch summaries agree with frozen Jo, default and release."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'search/regex_limits',
]
RELEASE = ['tests/cases/optimizer/record_return_loop.dewy', 'bench/parallel/mergesort.dewy', 'optimizer/constant_selections']


def test_inline_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0


def test_inline_ops_release_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, RELEASE, ('--release',)) > 0
