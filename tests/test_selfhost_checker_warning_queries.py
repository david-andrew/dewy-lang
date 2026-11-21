"""The mixed checker and its twin issue matching method, variable and discarded-result warnings."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_warning_queries_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    hidden = tmp_path / 'hidden.dewy'
    hidden.write_text('upper=(s:string):>string=>"<{s}>"\nmain=()=>printl("hi".upper)\n')
    visible = tmp_path / 'visible.dewy'
    visible.write_text('let score=0\nmain=():>void=>{let scroe=1 exit(42)}\n')
    dropped = tmp_path / 'dropped.dewy'
    dropped.write_text("describe=(n:int)=>{if $build.mode =? 'debug' {printl(n)}}\nmain=()=>describe(1)\n")
    discarded = tmp_path / 'discarded.jo'
    discarded.write_text('main = ():\n    s = "abc"\n    upper(s)\n    return 0\n')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_warning_queries',),
                             (hidden, visible, dropped, discarded), flags=((), ('--release',)))
    for path, flags, status, _, stderr, _ in results:
        assert status == 0, (path, flags, stderr)
    assert all('hides the library' in r[4] for r in results[:2])
    assert all("did you mean the visible variable 'score'" in r[4] for r in results[2:4])
    assert all('never used' not in r[4] for r in results[4:6])
    assert all('leaves its argument as it was' in r[4] for r in results[6:])
