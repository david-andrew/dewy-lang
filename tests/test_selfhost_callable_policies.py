"""Named functions, lambdas and partials capture policy at their creation site in both compilers."""

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401
from tests.test_settingsplace_defaults import SOURCE


def test_callable_policies_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    programs = []
    for name, value in [('named', '@shown'), ('lambda', '()=>shown()'), ('partial', '@show(42)')]:
        source = tmp_path / f'{name}.dewy'
        source.write_text('''$runtime_checks
shown=()=>printl($time.zone)
show=(n:int64)=>{printl(n); printl($time.zone)}
make=()=>{
    $time.zone='UTC'
    VALUE
}
main=()=>{let saved=make; saved()}
'''.replace('VALUE', value))
        programs.append(source)
    computed = tmp_path / 'computed.dewy'
    computed.write_text(SOURCE)
    results = compare_builds(compiler, tmp_path, monkeypatch, ('callable_policies',), [*programs, computed])
    assert [r[2] == 0 for r in results] == [True, True, True, False]
    assert 'computed or setting-dependent defaults' in results[-1][4]
