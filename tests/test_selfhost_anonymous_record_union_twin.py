"""Anonymous record branches infer their fields before forming a union in both builds."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_anonymous_record_union_twin(compiler, tmp_path, monkeypatch):
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_conditionals',), [
        'tests/cases/anonymous_record_union/inferred.dewy',
        'tests/cases/anonymous_record_union/field_types.dewy',
        'tests/cases/anonymous_record_union/context.dewy',
    ])
    assert all(row[2] == 0 for row in results)
