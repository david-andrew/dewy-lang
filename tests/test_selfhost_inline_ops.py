"""Inlining policy and its branch summaries agree with frozen Jo, default and release."""
from tests.selfhost_facts_double import compare_moved
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

CASES = [
    'search/regex_limits',
]
RELEASE = ['tests/cases/optimizer/record_return_loop.dewy', 'bench/parallel/mergesort.dewy', 'optimizer/constant_selections']


def test_inline_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0


def test_inline_ops_release_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, RELEASE, ('--release',)) > 0


def test_inline_ops_whole_pass_matches_twin(compiler, tmp_path, monkeypatch):
    # The default fast path and release inliner both cross the moved boundary.
    results = compare_builds(compiler, tmp_path, monkeypatch, ('inline_ops',),
                             ('tests/ladder/96_ct_crypto/design.dewy',
                              'tests/cases/optimizer/record_return_loop.dewy',
                              'compiler/main.jo'),
                             flags=((), ('--release',)))
    assert all(row[2] == 0 for row in results), [(row[0], row[1], row[2], row[4][-300:]) for row in results]
