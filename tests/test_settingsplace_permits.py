"""A cap counts active descendants, including nested joins and waiting-lane tasks."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401

LEAF = '''
$runtime_checks
leaf=(active:Atomic<int64> peak:Atomic<int64>):>int64=>{
 let count=active.add(1)
 peak.set_max(count)
 let total:int64=0
 loop i in [0..30000) {total+=i xor active.load}
 active.add(-1);
 total
}
'''


def run(compiler, tmp_path, source, flags=()):
    path = tmp_path / 'permits.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'run', path, *flags], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '42\n', result.stdout


@pytest.mark.parametrize('flags', [(), ('--release',)])
@pytest.mark.parametrize('cores', [1, 2])
def test_nested_joins_share_ancestor_permits(compiler, tmp_path, flags, cores):
    run(compiler, tmp_path, LEAF + '''
child=(active:Atomic<int64> peak:Atomic<int64>):>int64=>{
 $program.max_cores=2
 let xs=[parallel i in [0..16) leaf(active peak)]
 xs.length
}
work=(cores:int<(>=? 1)>):>void=>{
 $program.max_cores=cores
 let active=atomic(0)
 let peak=atomic(0)
 let xs=[parallel i in [0..8) child(active peak)]
 $runtime_assert(xs.length =? 8)
 $runtime_assert(active.load =? 0)
 $runtime_assert(peak.load >=? 1 and peak.load <=? available_cores)
 printl(42)
}
main=()=>work('''+str(cores)+')\n', flags)


@pytest.mark.parametrize('cores', [1, 2])
def test_cpu_bound_tasks_share_permits_and_join_yields(compiler, tmp_path, cores):
    run(compiler, tmp_path, LEAF + '''
work=(cores:int<(>=? 1)>):>void=>{
 $program.max_cores=cores
 let active=atomic(0)
 let peak=atomic(0)
 concurrent group {
  loop i in [0..8) {spawn(group) leaf(active peak);}
 }
 $runtime_assert(active.load =? 0)
 $runtime_assert(peak.load >=? 1 and peak.load <=? available_cores)
 printl(42)
}
main=()=>work('''+str(cores)+')\n')


def test_library_cap_cannot_raise_header_default_or_active_cap(compiler, tmp_path):
    (tmp_path/'lib.dewy').write_text('work=()=>{\n$program.max_cores=2\nprintl(available_cores)\n}\n')
    source=tmp_path/'app.dewy'
    source.write_text('''$program.max_cores=1
import p"lib.dewy" as lib
small=()=>{
 $program.max_cores=1
 lib.work()
}
main=()=>{lib.work();small()}
''')
    result=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout == '1\n1\n'


def test_policy_cleanup_keeps_the_live_permit_owner(compiler,tmp_path):
    (tmp_path/'probe.jo').write_text("""invariant = () -> bool:
    p = __settings_core_held()
    p == null or p.kind == 0
""")
    source=tmp_path/'app.dewy'
    source.write_text("""$runtime_checks
import p"probe.jo" as probe
work=()=>{
 $time.zone='UTC'
 $program.max_cores=1
}
main=()=>{
 $program.max_cores=1
 let saved=@work
 loop i in [0..8) {
  saved()
  $runtime_assert(probe.invariant)
  sleep(1ms);
 }
 printl(42)
}
""")
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\n'


@pytest.mark.parametrize('cores',[1,2])
def test_entry_header_budget_is_shared_by_cpu_bound_tasks(compiler,tmp_path,cores):
    run(compiler,tmp_path,'$program.max_cores='+str(cores)+'\n'+LEAF+"""
main=()=>{
 let active=atomic(0)
 let peak=atomic(0)
 concurrent group {loop i in [0..8) {spawn(group) leaf(active peak);}}
 $runtime_assert(active.load =? 0)
 $runtime_assert(peak.load >=? 1 and peak.load <=? available_cores)
 printl(42)
}
""")


def test_entry_cap_can_replace_the_header_default(compiler,tmp_path):
    import os
    if not hasattr(os,'sched_getaffinity') or len(os.sched_getaffinity(0))<2:
        pytest.skip('requires two available CPUs')
    source=tmp_path/'app.dewy'
    source.write_text("""$program.max_cores=1
server=()=>{
 $program.max_cores=2
 printl(available_cores)
}
main=()=>{printl(available_cores);server();printl(available_cores)}
""")
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='1\n2\n1\n'
