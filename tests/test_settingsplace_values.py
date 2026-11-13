"""A function value captures policies at creation, while caps follow its caller."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags',[(),('--release',)])
@pytest.mark.parametrize('value',['@shown','()=>printl($time.zone)'])
def test_handle_retains_policy_after_creation_scope_returns(compiler,tmp_path,flags,value):
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
shown=()=>printl($time.zone)
make=()=>{
 $time.zone='America/New_York'
 VALUE
}
call=(f:<():>void>)=>{
 $time.zone='UTC'
 f()
 printl($time.zone)
}
main=()=>{let saved=make;call(@saved)}
'''.replace('VALUE',value))
    r=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='America/New_York\nUTC\n'


def test_handle_captures_absence_and_not_creation_cap(compiler,tmp_path):
    source=tmp_path/'app.dewy'
    source.write_text('''$runtime_checks
shown=()=>{printl($time.zone);printl(available_cores)}
make=()=>{
 $program.max_cores=2
 @shown
}
call=(f:<():>void>)=>{
 $time.zone='UTC'
 $program.max_cores=1
 f()
}
main=()=>{let saved=make;call(@saved)}
''')
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='none\n1\n'


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_partial_application_captures_policies_at_creation(compiler,tmp_path,flags):
    source=tmp_path/'app.dewy'
    source.write_text("""$runtime_checks
shown=(n:int64)=>{printl(n);printl($time.zone)}
make=()=>{
 $time.zone='America/New_York'
 @shown(42)
}
call=(f:<():>void>)=>{
 $time.zone='UTC'
 f()
}
main=()=>{let saved=make;call(@saved)}
""")
    r=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\nAmerica/New_York\n'


def test_setting_defaults_have_an_explicit_capture_diagnostic(compiler,tmp_path):
    source=tmp_path/'app.dewy'
    source.write_text("""work=()=>{
 $time.zone='UTC'
 let f=@today
 printl(f)
}
main=()=>work()
""")
    r=subprocess.run([compiler,'check',source],capture_output=True,text=True,timeout=90)
    assert r.returncode!=0
    assert 'setting-dependent defaults is not yet supported' in r.stderr,r.stderr


def test_build_zone_frame_uses_the_compile_time_name(compiler,tmp_path):
    import os
    source=tmp_path/'app.dewy'
    source.write_text("""shown=()=>printl($time.zone)
work=()=>{
 $time.zone='build'
 shown()
}
main=()=>work()
""")
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,
                     env=dict(os.environ,TZ='UTC'),timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='UTC\n'


def test_build_zone_header_stays_pinned_when_scoped_zones_exist(compiler,tmp_path):
    import os
    source=tmp_path/'app.dewy'
    source.write_text("""$time.zone='build'
shown=()=>printl($time.zone)
work=()=>{
 $time.zone='Asia/Tokyo'
 shown()
}
main=()=>{shown();work();shown()}
""")
    r=subprocess.run([compiler,'run',source],capture_output=True,text=True,
                     env=dict(os.environ,TZ='UTC'),timeout=90)
    assert r.returncode==0,r.stderr
    assert r.stdout=='UTC\nAsia/Tokyo\nUTC\n'
