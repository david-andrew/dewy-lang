"""Rare refinement paths (string sets, totaldict checks, self-length growth and stores, length
contracts, resolved limits, record conversions) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('self_length', 'length_in_place', 'refinements', 'refinement_aggregates', 'record_field_shape', 'sibling_length')


def test_refine_rare_matches_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    files += sorted((ROOT / 'tests/cases').glob('*/*totaldict*.dewy'))
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('refine_rare',), paths)
    assert sum(r[2] == 0 for r in results) > 50 and sum(r[2] != 0 for r in results) > 20
