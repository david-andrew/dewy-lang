"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/rational_float_bounds/non_nan.dewy',
    'tests/cases/optimizer/return_facts_float.dewy',
    'tests/cases/float_constants/reject_inf_in_scope.dewy',
)


def test_numeric_constants_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('numeric_constants',), PATHS)
