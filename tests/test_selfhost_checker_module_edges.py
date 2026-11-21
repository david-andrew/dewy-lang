"""Module provenance and use order select the same names with either checker."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_module_edges_twins(compiler, tmp_path, monkeypatch):
    (tmp_path / 'a.jo').write_text('first = () -> int: 5\n')
    (tmp_path / 'b.jo').write_text("use 'a.jo'\nsecond = () -> int: first()\n")
    entry = tmp_path / 'entry.jo'
    entry.write_text("use 'b.jo'\nuse 'a.jo'\nmain = ():\n    print(first() + second())\n")
    paths = (entry, 'tests/cases/modules/splat_shadows_prelude.dewy',
             'tests/cases/modules/splat_selective_collision.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_module_edges',), paths)
    assert results[0][2] == results[1][2] == 0
    assert results[2][2] != 0
