"""Counted cursors, custom indexed sequences and next-method iterators produce matching builds."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_iterator_rewrites_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/grapheme/zipped_loop.dewy', 'tests/cases/sequence/counted.dewy',
             'tests/cases/loop/iterator_place_steps.dewy', 'tests/cases/loop/iterator_tree_walk.dewy',
             'tests/cases/sequence/mutable_custom.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_iterator_rewrites',), paths)
    assert all(r[2] == 0 for r in results[:-1])
    assert results[-1][2] != 0
