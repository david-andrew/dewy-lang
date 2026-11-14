"""Path field and collection contracts survive semantic types and frozen leaves."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES=sorted((ROOT/'tests/cases/decided_path_contracts').glob('*.dewy'))

def test_decided_safe_path_contract_twins(compiler,tmp_path,monkeypatch):
    compare_builds(compiler,tmp_path,monkeypatch,('safe_path_walk','type_format','checker_type_tests','checks_istype','checker_alias','checks_type_hooks','refine_rare','checker_literals','type_match','checker_members','checker_match','checks_match_hooks','checker_call_resolve','checker_call_values'),CASES,
                   flags=((),('--release',)))
