"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/unpack/param_captured_copy.dewy',
    'tests/cases/type_members/named.dewy',
    'tests/cases/object/intersections.dewy',
    'tests/cases/json/typed_dynamic_value.dewy',
    'tests/cases/closure/private_function_cycle.dewy',
)


def test_expr_cold_queries_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('expr_cold_queries',), PATHS)
