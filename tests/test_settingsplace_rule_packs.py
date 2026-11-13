"""Runtime-selected embedded packs leave existing zone values pinned."""
from pathlib import Path
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_values_keep_their_creation_pack_after_return(compiler,flags):
    source=ROOT/'tests/cases/settingsplace_rules/pinned.dewy'
    result=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout==source.with_suffix('.out').read_text()


def test_bad_embedded_pack_is_rejected_before_a_profile_runs(compiler,tmp_path):
    (tmp_path/'bad.bin').write_bytes(b'not a pack')
    source=tmp_path/'app.dewy'
    source.write_text("profile=()=>{\n$time.rules='bad.bin'\nprintl(42)\n}\nmain=(argv:array<string>)=>{if argv.length >? 1 {profile()}}\n")
    result=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert result.returncode!=0
    assert 'not a rule pack' in result.stderr,result.stderr


def test_unbounded_pack_paths_have_an_explicit_diagnostic(compiler,tmp_path):
    source=tmp_path/'app.dewy'
    source.write_text("profile=(path:string)=>{\n$time.rules=path\nprintl(42)\n}\nmain=()=>profile('x.bin')\n")
    result=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert result.returncode!=0
    assert 'run-time rule-pack paths are not yet supported' in result.stderr,result.stderr


def test_task_keeps_pack_after_its_launch_scope_returns(compiler,tmp_path):
    (tmp_path/'a.bin').write_bytes((ROOT/'tests/cases/settingsplace_rules/a.bin').read_bytes())
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
worker=(ready:Atomic<int64>)=>{
 loop ready.load =? 0 {sleep(1ms);}
 printl($time.rules)
}
launch=(group:TaskGroup ready:Atomic<int64>)=>{
 $time.rules='a.bin'
 spawn(group) worker(ready)
}
main=()=>{
 let ready=atomic(0)
 concurrent group {
  launch(group ready)
  $runtime_assert($time.rules is? none)
  ready.store(1)
 }
}
''')
    result=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='a.bin\n'


def test_zone_setting_retains_handle_without_switching_active_pack(compiler,tmp_path):
    for name in ['a.bin','b.bin']:
        (tmp_path/name).write_bytes((ROOT/'tests/cases/settingsplace_rules'/name).read_bytes())
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
make=(name:string)=>{
 $time.rules='a.bin'
 zone(name) or_throw
}
profile=(z:Zone)=>{
 $time.rules='b.bin'
 $time.zone=z
 let text:string='2026-07-01T12:00'
 printl(zoned(text fold='earlier' gap='next') or_throw)
 let name:string='Test/Zone'
 let fresh=zone(name) or_throw
 printl(zoned(text zone=fresh fold='earlier' gap='next') or_throw)
}
main=()=>profile(make("Test/Zone") or_throw)
''')
    result=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='2026-07-01T12:00:00+03:00[Test/Zone]\n2026-07-01T12:00:00+04:00[Test/Zone]\n'


def test_header_and_scoped_copy_of_one_pack_have_one_identity(compiler,tmp_path):
    (tmp_path/'a.bin').write_bytes((ROOT/'tests/cases/settingsplace_rules/a.bin').read_bytes())
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
$time.rules='a.bin'
scoped=(old:Zone)=>{
 $time.rules='a.bin'
 let name:string='Test/Zone'
 let current=zone(name) or_throw
 printl(old =? current)
}
main=()=>{
 let name:string='Test/Zone'
 let old=zone(name) or_throw
 scoped(old)
}
''')
    result=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='true\n'


def test_host_freshness_probe_uses_a_private_task_cache(compiler,tmp_path):
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
import p"@lib/time/zones.dewy" as zones
worker=()=>{
 let name:string='UTC'
 let z=zone(name) or_throw
 printl(zones._zone_pack_status(z))
}
main=()=>{concurrent {spawn worker()}}
''')
    result=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr


def test_zone_lookups_are_safe_in_tasks(compiler,tmp_path):
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
worker=(name:string)=>printl(zone(name))
main=()=>{concurrent {spawn worker("UTC")}}
''')
    result=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    result=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert 'UTC' in result.stdout


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_task_zone_operations_keep_inherited_pack_and_zone_after_return(compiler,tmp_path,flags):
    for name in ['a.bin','b.bin']:
        (tmp_path/name).write_bytes((ROOT/'tests/cases/settingsplace_rules'/name).read_bytes())
    source=tmp_path/'app.dewy'
    source.write_text("""$runtime_checks
worker=(ready:Atomic<int64>)=>{
 loop ready.load =? 0 {sleep(1ms);}
 let text:string='2026-07-01T12:00'
 printl(zoned(text fold='earlier' gap='next') or_throw)
}
launch=(group:TaskGroup ready:Atomic<int64>)=>{
 $time.rules='a.bin'
 $time.zone='Test/Zone'
 spawn(group) worker(ready)
}
main=()=>{
 $time.rules='b.bin'
 let ready=atomic(0)
 concurrent group {
  launch(group ready)
  ready.store(1)
 }
}
""")
    result=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='2026-07-01T12:00:00+03:00[Test/Zone]\n'


@pytest.mark.parametrize('program',[
    'main=()=>printl($memory_left)\n',
    'main=()=>{\n$memory_left\n}\n',
    '$memory_left\n',
])
def test_memory_left_reports_missing_accounting(compiler,tmp_path,program):
    source=tmp_path/'memory.dewy'
    source.write_text(program)
    result=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert result.returncode!=0
    assert '`$memory_left` is not yet supported' in result.stderr,result.stderr


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_zone_values_keep_their_source_across_scope_changes(compiler,tmp_path,flags):
    import os
    from tests.test_time_zone_source import tzif
    (tmp_path/'a.bin').write_bytes((ROOT/'tests/cases/settingsplace_rules/a.bin').read_bytes())
    host=tmp_path/'host'/'Test'
    host.mkdir(parents=True)
    (host/'Zone').write_bytes(tzif(5*3600,b'<+05>-5'))
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
$time.rules='a.bin'
show=(z:Zone)=>{
 let text:string='2026-07-01T12:00'
 printl(zoned(text zone=z fold='earlier' gap='next') or_throw)
}
host=(old:Zone)=>{
 $time.zone_source='host'
 let name:string='Test/Zone'
 let fresh=zone(name) or_throw
 show(old) or_throw
 show(fresh) or_throw
 fresh
}
main=()=>{
 let name:string='Test/Zone'
 let old=zone(name) or_throw
 let fresh=host(old) or_throw
 show(fresh) or_throw
 show(old) or_throw
}
''')
    env=dict(os.environ,TZDIR=str(host.parent))
    r=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,env=env,timeout=90)
    assert r.returncode==0,r.stderr
    assert [line.split('T12:00:00')[1] for line in r.stdout.splitlines()]==[
        '+03:00[Test/Zone]','+05:00[Test/Zone]','+05:00[Test/Zone]','+03:00[Test/Zone]']


def test_tasks_publish_one_host_fallback_warning(compiler,tmp_path):
    import os
    source=tmp_path/'app.dewy'
    source.write_text("""$runtime_checks
$time.zone_source='host'
worker=(name:string)=>{
 let text:string='2026-07-01T12:00'
 let z=zone(name) or_throw
 printl(zoned(text zone=z fold='earlier' gap='next') or_throw)
}
main=()=>{concurrent group {loop i in [0..4) {spawn(group) worker("UTC");}}}
""")
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,
                     env=dict(os.environ,TZDIR=str(tmp_path/'missing')),timeout=90)
    assert r.returncode==0,r.stderr
    assert len(r.stdout.splitlines())==4
    assert r.stderr.count('this machine has no rules for UTC')==1,r.stderr


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_task_calendar_and_system_zone_apis_are_safe(compiler,tmp_path,flags):
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
import p"@lib/time/zones.dewy" as zones
worker=()=>{
 let date=today
 $runtime_assert(date.year >=? 2000)
 let system=zones.system_zone
 $runtime_assert(system.name.length >? 0)
 printl(42)
}
main=()=>{
 $time.zone='UTC'
 concurrent {spawn worker()}
}
''')
    r=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\n'
