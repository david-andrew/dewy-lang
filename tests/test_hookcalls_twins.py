"""Hooked calls and predicate cleanup agree with the frozen effect/facts leaves."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_hookcalls_twins(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in
             sorted((ROOT / 'tests/cases/hookcalls').glob('*.dewy'))]
    result = compare_builds(compiler, tmp_path, monkeypatch,
                           ('effect_scan', 'facts_forgets', 'predicate_summaries'),
                           paths, flags=((), ('--release',)))
    assert result
    for row in result:
        path, flags, status = row[:3]
        rejected = (ROOT / path).with_suffix('.err').exists()
        assert (status != 0) == rejected, (path, flags, status)
