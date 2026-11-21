"""Unread locals have the same location and proposed spelling in Jo and Dewy sources."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_local_warnings_twins(compiler, tmp_path, monkeypatch):
    jo = tmp_path / 'unused.jo'
    jo.write_text('score = 0\nmain = ():\n    scor = 1\n    print(score)\n')
    dewy = tmp_path / 'unused.dewy'
    dewy.write_text('let score=0\nmain=()=>{let scroe=1 let _reserve=2 printl(score)}\n')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_local_warnings',), (jo, dewy))
    for r in results:
        assert r[2] == 0 and 'but never used' in r[4]
    assert "did you mean the variable 'score'" in results[0][4]
    assert "did you mean the visible variable 'score'" in results[1][4]
    assert "'_reserve' is given a value" not in results[1][4]
