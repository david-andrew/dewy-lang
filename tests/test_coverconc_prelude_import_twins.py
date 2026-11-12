"""Explicit and lazy imports retain one prelude module identity."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_prelude_import_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in
             sorted((ROOT / 'tests/cases/coverconc_prelude_imports').glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('prelude_ops',),
                            paths, flags=((), ('--release',)))
    assert results and all(row[2] == 0 for row in results), [row[:5] for row in results]
