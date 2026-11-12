"""Nullable-source diagnostics and record wrappers agree with frozen twins."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_merged_nullable_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in
             sorted((ROOT / 'tests/cases/coverconc_merged_nullable').glob('*.dewy'))]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('merged_checks',),
                            paths, flags=((), ('--release',)))
    positives = [row for row in results
                 if row[0].endswith(('wrapped.dewy', 'shadow.dewy'))]
    assert all(row[2] == 0 for row in positives), '\n'.join(row[4] for row in positives)
    assert sum(row[2] == 0 for row in results) == 4
    assert sum(row[2] != 0 for row in results) == 12
