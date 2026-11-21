"""Demanded library function bodies produce the same code as the frozen checker."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_lazy_body_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/ladder/97_notes_service/design.dewy', 'tests/ladder/01_word_count/core.dewy')
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_lazy_body',), paths)
    assert all(r[2] == 0 for r in rows)
