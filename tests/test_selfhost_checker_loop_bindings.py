"""Destructuring a loop binder preserves nested patterns, mutable dictionary iteration and diagnostics."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_loop_bindings_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/unpack/loop_nested_array.dewy', 'tests/cases/unpack/loop_nested_map.dewy',
             'tests/cases/unpack/leaf_types_loop_dictionary.dewy', 'tests/cases/sequence/mutable_pattern.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_loop_bindings',), paths)
    assert all(r[2] == 0 for r in results[:-1])
    assert results[-1][2] != 0
