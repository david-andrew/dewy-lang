"""Runtime scopes and inherited checker instances match all changed frozen leaves."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_settingsplace_twins(compiler, tmp_path, monkeypatch):
    path = tmp_path / 'policies.dewy'
    path.write_text('''
$runtime_checks
read=(xs:array<int64> i:int64):>int64=>xs[i]
work=()=>{
 $time.zone='UTC'
 printl(read([42] 0))
 parallel {printl($time.zone)}
}
main=()=>work()
''')
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('dewy_reader_host', 'dewy_reader_state',
                    'reader_service_ops', 'setting_scopes', 'program_settings',
                    'directive_ops', 'directive_queries', 'checker_instances',
                    'checker_program', 'parallel_ops', 'checks_thin_expr', 'poly_ops'), [path], flags=((), ('--release',)))


def test_settingsplace_reader_twins(compiler, tmp_path):
    from tools.compiler.parser_diff import build_pair, compare
    # dewy_file and dewy_reader use the complete frozen seed as one unit.
    pair = build_pair(compiler, tmp_path, release=False)
    path = tmp_path / 'scope.dewy'
    path.write_text("$runtime_checks\nmain=()=>{\n$program.max_cores=1\nprintl(available_cores)\n}\n")
    assert compare(pair, [path], tmp_path, release=False, workers=1) == []
