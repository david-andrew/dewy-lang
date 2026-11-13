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
    floats = tmp_path / 'floats.dewy'
    floats.write_text("$runtime_checks\nscale=(x:float64):>float64=>x*2.0\nstrict=()=>{\n$no_inf\nprintl(scale(1.0))\n}\nmain=()=>strict()\n")
    header = tmp_path / 'header.dewy'
    header.write_text("$runtime_checks\n$program.max_cores=1\nmain=()=>{concurrent {spawn printl(42)}}\n")
    values = tmp_path / 'values.dewy'
    values.write_text("""$runtime_checks
shown=()=>printl($time.zone)
make=()=>{
 $time.zone='UTC'
 @shown
}
invoke=(f:<():>void>)=>{
 $time.zone='Asia/Tokyo'
 f()
}
main=()=>{let f=make;invoke(@f)}
""")
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('dewy_reader_host', 'dewy_reader_state',
                    'reader_service_ops', 'setting_scopes', 'program_settings',
                    'directive_ops', 'directive_queries', 'checker_instances',
                    'checker_program', 'parallel_ops', 'checks_thin_expr', 'poly_ops', 'float_ops', 'copy_ops', 'lower_functions', 'deadlock_walk', 'deadlock_certificates', 'checker_call_values', 'concurrency_tasks', 'concurrency_waits', 'constant_checks', 'lower_races', 'partial_checks'), [path, floats, header, values], flags=((), ('--release',)))


def test_settingsplace_reader_twins(compiler, tmp_path):
    from tools.compiler.parser_diff import build_pair, compare
    # dewy_file and dewy_reader use the complete frozen seed as one unit.
    pair = build_pair(compiler, tmp_path, release=False)
    path = tmp_path / 'scope.dewy'
    path.write_text("$runtime_checks\nmain=()=>{\n$program.max_cores=1\nprintl(available_cores)\n}\n")
    memory = tmp_path / 'memory.dewy'
    memory.write_text('main=()=>{\n$memory_left\n}\n')
    header = tmp_path / 'memory_header.dewy'
    header.write_text('$memory_left\n')
    assert compare(pair, [path, memory, header], tmp_path, release=False, workers=1) == []
