"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/tensor_shape_flow/shapes_flow.dewy',
    'tests/cases/numeric/range_bracket_constructors.dewy',
    'tests/cases/membership/range_snapshot.dewy',
    'tests/cases/slice_assign_extents/one_wider.dewy',
    'tests/cases/membership/float_range.dewy',
)


def test_range_checks_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('range_checks',), PATHS)
