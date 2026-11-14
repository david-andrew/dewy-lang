"""Unscoped setting restoration matches its lowering and desugaring twins."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401


def test_coverweek_setting_scopes_lower_group_twins(compiler, tmp_path, monkeypatch):
    paths = sorted(str(p.relative_to(ROOT)) for p in
                   (ROOT / 'tests/cases/coverweek').glob('settings_*.dewy'))
    compare_builds(compiler, tmp_path, monkeypatch,
                   ('setting_scopes', 'lower_group'), paths,
                   flags=((), ('--release',)))


def test_coverweek_ownership_checks_types_twins(compiler, tmp_path, monkeypatch):
    paths = [str(ROOT / 'tests/cases/coverweek' / (name + '.dewy')) for name in
             ('settings_parenthesized_extent', 'parallel_failure_own_payload',
              'parallel_failure_sibling_owner', 'hooks_parallel_dependency_move', 'hooks_task_transfer')]
    ordinary = tmp_path / 'ordinary_callback.dewy'
    ordinary.write_text("""Ticket=type of [id:int64 $__drop__=():>void=>printl"released"]
run=(f:<():>void>)=>f()
main=()=>{
 $time.zone='UTC'
 let ticket=Ticket[8]
 run(()=>printl(ticket.id))
}
""")
    paths.append(str(ordinary))
    result = compare_builds(compiler, tmp_path, monkeypatch,
                           ('ownership_checks', 'ownership_types', 'concurrency_tasks'), paths,
                           flags=((), ('--release',)))
    assert all(row[2] != 0 and 'erase capture ownership' in row[4] for row in result[-2:])


def test_coverweek_dewy_reader_twins(compiler, tmp_path):
    from tools.compiler import parser_diff
    paths = [ROOT / 'tests/cases/coverweek' / (name + '.dewy') for name in
             ('settings_parallel_lets', 'settings_parenthesized_extent', 'settings_task_snapshot')]
    pair = parser_diff.build_pair(compiler, tmp_path, release=False)
    failures = parser_diff.compare(pair, paths, tmp_path, release=False, workers=1)
    assert not failures, failures


def test_coverweek_deadlock_walk_policy_callback_twins(compiler, tmp_path, monkeypatch):
    paths = [str(ROOT / 'tests/cases/coverweek' / (name + '.dewy')) for name in
             ('signals_helper_policy', 'settings_task_snapshot', 'settings_parallel_lets')]
    stuck = tmp_path / 'wrapped_missing_sender.dewy'
    stuck.write_text("""main=()=>{
 $time.zone='UTC'
 let incoming=channel<int64>(1)
 concurrent {
  spawn {incoming.receive or_throw;}
  incoming.receive or_throw;
 }
}
""")
    paths.append(str(stuck))
    result = compare_builds(compiler, tmp_path, monkeypatch, ('deadlock_walk',), paths,
                            flags=((), ('--release',)))
    assert all(row[2] != 0 and 'waits forever' in row[4] for row in result[-2:])
