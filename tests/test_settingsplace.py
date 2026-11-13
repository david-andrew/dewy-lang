"""Top-of-scope settings survive calls, tasks and exceptional exits."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, *args):
    path = tmp_path / 'settings.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'run', path, *args], capture_output=True,
                            text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize('blank', ['', '\n', '\n\n'])
def test_file_settings_ignore_blank_lines(compiler, tmp_path, blank):
    assert run(compiler, tmp_path, '$runtime_checks\n' + blank + '''
read=(xs:array<int64> i:int64):>int64=>xs[i]
main=()=>printl(read([42] 0))
''') == '42\n'


def test_function_checks_follow_transitive_calls(compiler, tmp_path):
    assert run(compiler, tmp_path, '''
read=(xs:array<int64> i:int64):>int64=>xs[i]
bridge=(xs:array<int64> i:int64):>int64=>read(xs i)
checked=():>void=>{
 $runtime_checks
 printl(bridge([42] 0))
}
main=()=>checked()
''') == '42\n'


def test_runtime_profiles_restore_and_narrow(compiler, tmp_path):
    # Compare against hardware without assuming how many CPUs the test host has.
    assert run(compiler, tmp_path, '''
$runtime_checks
$program.max_cores=2
report=(expected:int64):>void=>$runtime_assert(available_cores =? expected)
small=():>void=>{
 $program.max_cores=1
 report(1)
}
wide=(limit:int64<(>=? 1)>):>void=>{
 $program.max_cores=limit
 report(limit)
 small()
 report(limit)
}
main=()=>{
 report(2)
 wide(2)
 report(2)
 printl(42)
}
''') == '42\n'


def test_tasks_inherit_policy_after_launch_scope_returns(compiler, tmp_path):
    assert run(compiler, tmp_path, '''
$runtime_checks
work=(ready:Atomic<int64>):>void=>{
 loop ready.load() =? 0 {sleep(1ms);}
 $runtime_assert($time.zone =? 'UTC')
 $runtime_assert(available_cores =? 1)
}
launch=(group:TaskGroup ready:Atomic<int64>):>void=>{
 $time.zone='UTC'
 $program.max_cores=1
 spawn(group) work(ready)
}
main=()=>{
 let ready=atomic(0)
 concurrent group {
  launch(group ready)
  $runtime_assert($time.zone is? none)
  ready.store(1)
 }
 printl(42)
}
''') == '42\n'


def test_runtime_fast_math_evaluates_once(compiler, tmp_path):
    assert run(compiler, tmp_path, '''
$runtime_checks
choose=(hits:Atomic<int64>):>bool=>{hits.add(1); return true}
work=(hits:Atomic<int64>):>void=>{
 $fast_math=choose(hits)
 printl(42)
}
main=()=>{
 let hits=atomic(0)
 work(hits)
 $runtime_assert(hits.load() =? 1)
}
''') == '42\n'


@pytest.mark.parametrize('source', [
 'f=()=>42\n$runtime_checks\nmain=()=>printl(f)\n',
 'main=()=>{printl(42)\n$runtime_checks\n}\n',
 'main=()=>$runtime_checks {printl(42)}\n',
])
def test_misplaced_settings_name_their_scope(compiler, tmp_path, source):
    path = tmp_path / 'misplaced.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'top of' in result.stderr and ('inside' in result.stderr or "top of that function's body" in result.stderr or 'before the first statement' in result.stderr), result.stderr


def test_handles_retain_their_creation_policy(compiler, tmp_path):
    assert run(compiler, tmp_path, '''
$runtime_checks
shown=():>void=>printl($time.zone)
invoke=(callback:<():>void>):>void=>{
 $time.zone='Asia/Tokyo'
 callback()
}
inside=():><():>void>=>{
 $time.zone='UTC'
 @shown
}
main=()=>{
 invoke(@shown)
 invoke(inside)
 invoke(()=>printl($time.zone))
 printl(42)
}
''') == 'none\nUTC\nnone\n42\n'


def test_setting_expressions_run_in_written_order(compiler, tmp_path):
    assert run(compiler, tmp_path, '''choose_cores=():>int<(>=? 1)>=>{printl(1); return 1}
choose_fast=():>bool=>{printl(2); return true}
main=()=>{
 $program.max_cores=choose_cores
 $fast_math=choose_fast
 printl(42)
}
''') == '1\n2\n42\n'


def test_checked_and_static_instances_are_distinct(compiler, tmp_path):
    path = tmp_path / 'variants.dewy'
    path.write_text('''read=(xs:array<int64> i:int64):>int64=>xs[i]
checked=(xs:array<int64> i:int64):>int64=>{
 $runtime_checks
 read(xs i)
}
strict=(xs:array<int64> i:int64):>int64=>{
 $runtime_checks=false
 read(xs i)
}
main=()=>{printl(checked([42] 0)); printl(strict([42] 0))}
''')
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert 'cannot prove index is in bounds' in result.stderr, result.stderr


def test_zone_value_policy_restores_after_call(compiler, tmp_path):
    assert run(compiler, tmp_path, '''shown=()=>printl($time.zone)
profile=(value:Zone):>void=>{
 $time.zone=value
 shown()
}
main=()=>{
 let value=zone("UTC") or_throw
 profile(value)
 shown()
}
''') == 'UTC\nnone\n'


def test_imported_policy_does_not_retarget_a_called_handle(compiler, tmp_path):
    (tmp_path / 'library.dewy').write_text('''invoke=(callback:<():>void>):>void=>{
 $time.zone='Asia/Tokyo'
 callback()
}
''')
    assert run(compiler, tmp_path, '''import p"library.dewy" as library
shown=():>void=>printl($time.zone)
main=()=>library.invoke(@shown)
''') == 'none\n'


@pytest.mark.parametrize('value,found', [("'2'", 'string'), ('true', 'bool'), ('2.5', 'rational')])
def test_function_core_cap_keeps_integer_contract(compiler, tmp_path, value, found):
    path = tmp_path / 'bad_cap.dewy'
    path.write_text(f'main=()=>{{\n$program.max_cores={value}\nprintl(42)\n}}\n')
    result = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert f"argument 'cores' expects int<refinement>, found {found}" in result.stderr, result.stderr


def test_guarded_mathematical_integer_core_count(compiler, tmp_path):
    assert run(compiler, tmp_path, '''work=(cores:int):>void=>{
 if cores <? 1 {return}
 {
  $program.max_cores=cores
  printl(available_cores)
 }
}
main=()=>work(to_int("1") ?? 0)
''') == '1\n'


def test_entry_policy_defaults_reach_imported_functions(compiler, tmp_path):
    (tmp_path / 'library.dewy').write_text("$time.gap='reject'\nshown=()=>printl($time.gap)\n")
    assert run(compiler, tmp_path, '''$time.gap='next'
import p"library.dewy" as library
main=()=>library.shown()
''') == 'next\n'
