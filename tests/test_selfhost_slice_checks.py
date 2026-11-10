"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/rational/slice_update.dewy',
    'tests/cases/refine_length_helpers/slice_length_only_reject.dewy',
    'tests/cases/frontend/strings_string_diagnostics_4.dewy',
)


def test_slice_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('slice_checks',), PATHS)
