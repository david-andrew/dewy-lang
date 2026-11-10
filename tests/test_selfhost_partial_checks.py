"""Partial application, prepared waits and rest arguments agree with the frozen twin."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('partial', 'rest_params', 'select', 'select_named', 'select_sources', 'handle')


def test_partial_checks_match_twin(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for d in DIRS
             for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('partial_checks',), paths)
    assert any(r[2] == 0 for r in results) and any(r[2] != 0 for r in results)
