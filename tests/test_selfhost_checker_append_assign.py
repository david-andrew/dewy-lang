"""A Jo concatenation spine and a Dewy interpolation keep the order of the appended pieces."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_append_assign_twins(compiler, tmp_path, monkeypatch):
    jo = tmp_path / 'append.jo'
    jo.write_text('main = ():\n    s = "a"\n    s = s + "b" + "c"\n'
                  '    a = [1]\n    a = a + [2] + [3]\n    print(s)\n    print(a)\n')
    paths = (jo, 'tests/cases/string/interpolated_append.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_append_assign',), paths)
    assert all(r[2] == 0 for r in results)
