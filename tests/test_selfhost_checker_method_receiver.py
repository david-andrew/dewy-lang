"""Method lookup agrees on generic and overloaded first parameters and missing members."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_method_receiver_twins(compiler, tmp_path, monkeypatch):
    paths = ('tests/cases/expected_args/generic_receiver.dewy',
             'tests/cases/overload/group_empty_receiver.dewy',
             'tests/cases/surface/missing_member.dewy')
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_method_receiver',), paths)
    assert rows[0][2] == rows[1][2] == 0
    assert rows[2][2] != 0 and 'int64 has no member' in rows[2][4]
