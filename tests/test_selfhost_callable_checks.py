"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/handle/values.dewy',
    'tests/cases/handle/keeps_defaults.dewy',
    'tests/cases/layout/size_of_records.dewy',
    'tests/cases/callable/handle_variance.dewy',
    'tests/cases/witness/projection_call_divisor.dewy',
    'tests/cases/dictionary/rhs_bare_call_captured_removed_proof.dewy',
)


def test_callable_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('callable_checks',), PATHS)
