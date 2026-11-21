"""Optional fill and alias tracking preserve successful joins and diagnose invalidated fills."""

from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_optional_fill_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = sorted((ROOT / 'tests/cases/optional').glob('fill_join*.dewy'))
    results = compare_builds(compiler, tmp_path, monkeypatch, ('optional_fill',), cases)
    assert cases and any(p.with_suffix('.err').exists() for p in cases)
    assert [r[2] == 0 for r in results] == [not p.with_suffix('.err').exists() for p in cases]
