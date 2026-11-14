"""Specialized length and shape obligations agree with all changed frozen leaves."""
from tests.selfhost_build_double import build_all, compare_builds
from tests.test_selfhost_checked_eval import frozen_evaluator  # noqa: F401
from tests.support import ROOT, compiler  # noqa: F401

CASES=sorted((ROOT/'tests/cases/decided_generic_lengths').glob('*.dewy'))

def test_decided_generic_length_twins(compiler,tmp_path,monkeypatch):
    compare_builds(compiler,tmp_path,monkeypatch,
        ('type_value_arguments','checker_resolve','checks_ident_hooks','nd_contract_ops',
         'refine_rare','refine_resolve','type_refinement','type_substitute'),
        CASES,flags=((),('--release',)))


def test_decided_extent_checked_eval_twins(compiler, frozen_evaluator, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    expected = build_all(frozen_evaluator, tmp_path, 'frozen', CASES, flags=((), ('--release',)))
    got = build_all(compiler, tmp_path, 'live', CASES, flags=((), ('--release',)))
    assert got == expected
