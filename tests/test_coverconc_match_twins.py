"""Type patterns preserve the chosen union member when short names collide."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_union_match_twins(compiler, tmp_path, monkeypatch):
    paths = ['tests/cases/coverconc_match_names/control_name.dewy']
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_match',), paths,
                            flags=((), ('--release',)))
    assert all(row[2] == 0 for row in results)
