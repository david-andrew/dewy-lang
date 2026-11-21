"""Qualified members, generic families and builtins resolve to the same type or diagnostic."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_type_names_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/type_members/records.dewy', 'tests/cases/type_members/named.dewy',
             'tests/cases/secret/operations.dewy', 'tests/cases/decided_integer_arguments/qualified.dewy',
             'tests/cases/type_members/missing_member.dewy', 'tests/cases/surface/jo_type_annotation.dewy',
             'tests/cases/surface/jo_type_conversion.dewy', 'tests/cases/surface/jo_type_member.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_type_names',), paths)
    assert all(r[2] == 0 for r in results[:4])
    assert all(r[2] != 0 for r in results[4:])
