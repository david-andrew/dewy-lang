"""Stable record field proofs and mutation/hook fallbacks match frozen Jo."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES=sorted((ROOT/'tests/cases/decided_path_fields').glob('*.dewy'))

def test_decided_safe_path_walk_twins(compiler,tmp_path,monkeypatch):
    compare_builds(compiler,tmp_path,monkeypatch,('safe_path_walk',),CASES,
                   flags=((),('--release',)))
