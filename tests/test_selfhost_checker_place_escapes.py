"""Reject escaping places while accepting a returned function handle."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_place_escapes_twins(compiler, tmp_path, monkeypatch):
    handle = tmp_path / 'handle.dewy'
    handle.write_text('answer=()=>42\ngive=()=>@answer\nmain=()=>{let f=give(); printl(f())}\n')
    paths = ('tests/cases/argument/local_place_top_level.dewy',
             'tests/cases/argument/return_place.dewy', handle)
    rows = compare_builds(compiler, tmp_path, monkeypatch, ('checker_place_escapes',), paths)
    assert rows[0][2] != 0 and 'a global cannot be a place' in rows[0][4]
    assert rows[1][2] != 0 and 'a function gives back a value' in rows[1][4]
    assert rows[2][2] == 0
