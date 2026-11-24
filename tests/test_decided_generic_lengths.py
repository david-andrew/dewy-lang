"""Specialized length and shape obligations agree with all changed frozen leaves."""
from tests.selfhost_build_double import build_all, compare_builds, record_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES=sorted((ROOT/'tests/cases/decided_generic_lengths').glob('*.dewy'))

def test_decided_generic_length_twins(compiler,tmp_path,monkeypatch):
    compare_builds(compiler,tmp_path,monkeypatch,
        ('type_value_arguments','checker_resolve','checks_ident_hooks','nd_contract_ops',
         'refine_rare','refine_resolve','type_refinement','type_substitute'),
        CASES,flags=((),('--release',)))


def test_decided_extent_checked_eval_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    got = build_all(compiler, tmp_path, 'live', CASES, flags=((), ('--release',)))
    record_builds(got, tmp_path, 'live')
