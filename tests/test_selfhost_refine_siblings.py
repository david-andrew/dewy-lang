"""Sibling bounds and length-tied record fields (element and dictionary-value bounds, paired runs of
operations, their hints and runtime checks) agree with frozen Jo: the same messages and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DIRS = ('record_paired_fields', 'sibling_length', 'dict_sibling', 'self_length')


def test_refine_siblings_match_twin(compiler, tmp_path, monkeypatch):
    files = [p for d in DIRS for p in sorted((ROOT / 'tests/cases' / d).glob('*.dewy'))]
    paths = [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('refine_siblings',), paths)
    assert sum(r[2] == 0 for r in results) > 20 and sum(r[2] != 0 for r in results) > 20
