"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/comprehension/bracket_call.dewy',
    'tests/cases/optional/fill_join.dewy',
    'tests/cases/errors/forward_method_call.dewy',
    'tests/cases/witness/projection_call_divisor.dewy',
    'tests/cases/units/parameter_mismatch.dewy',
    'tests/cases/dogfood27_proofs/sum_lengths_hint.dewy',
)


def test_collection_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('collection_checks',), PATHS)
