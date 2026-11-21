"""The module name index chooses the same homes and reports the same ambiguous imports as its twin."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_home_index_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    paths = ('tests/ladder/98_notes_listen/design.dewy',
             'tests/cases/batch4_entry/splat.dewy',
             'tests/cases/modules/splat_selective_collision.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_home_index',), paths)
    assert results[0][2] == results[1][2] == 0
    assert results[2][2] != 0
