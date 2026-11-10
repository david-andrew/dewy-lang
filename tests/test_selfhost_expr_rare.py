"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/type_members/named.dewy',
    'tests/cases/units/temperature_points.dewy',
    'tests/cases/tensor/literal_shape_proven.dewy',
    'tests/cases/named_each/each.dewy',
    'tests/cases/library_contracts/physics_box_no_area.dewy',
    'tests/cases/errors/forward_method_call.dewy',
    'tests/cases/witness/projection_call_divisor.dewy',
    'tests/cases/units/parameter_mismatch.dewy',
    'tests/cases/type_members/named_twice.dewy',
)


def test_expr_rare_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('expr_rare',), PATHS)
