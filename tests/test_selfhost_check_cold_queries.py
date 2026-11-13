"""Cold expression helpers agree with the frozen twin on their existing golden cases."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

PATHS = (
    'tests/cases/units/conversions.dewy',
    'tests/cases/units/rvalue_series.dewy',
    'tests/cases/object/sibling_calls.dewy',
    'tests/cases/arena/reject_explicit_copies.dewy',
)


def test_check_cold_queries_match_twin(compiler, tmp_path, monkeypatch):
    compare_builds(compiler, tmp_path, monkeypatch, ('check_cold_queries',), PATHS)


def test_constant_query_reloads_values_after_evaluation(compiler, tmp_path, monkeypatch):
    source=tmp_path/'constant.jo'
    source.write_text('const enabled = not BOOTSTRAP and __setting_read("__core_caps")\nmain = (): print(enabled)\n')
    compare_builds(compiler, tmp_path, monkeypatch, ('check_cold_queries',), [source])
