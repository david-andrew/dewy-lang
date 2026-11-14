"""Named integer arguments use the same specialization as literal integers."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

CASES=sorted((ROOT/'tests/cases/decided_integer_arguments').glob('*.dewy'))

def test_type_value_arguments_match_twin(compiler,tmp_path,monkeypatch):
    compare_builds(compiler,tmp_path,monkeypatch,('type_value_arguments',),CASES,
                   flags=((),('--release',)))
