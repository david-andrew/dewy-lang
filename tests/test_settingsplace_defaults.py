"""Unimplemented default keepers cannot read a caller's time policy silently."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401

SOURCE = """get_zone=():>string?=>$time.zone
report_zone=(z:string?=get_zone)=>printl(z??'none')
make=()=>{
 $time.zone='UTC'
 @report_zone
}
other=()=>{
 $time.zone='Asia/Tokyo'
 let f=make
 f()
}
main=()=>other()
"""


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_indirect_time_defaults_are_rejected_and_the_lambda_works(compiler,tmp_path,flags):
    path=tmp_path/'app.dewy'
    path.write_text(SOURCE)
    rejected=subprocess.run([compiler,'check',path,*flags],capture_output=True,text=True,timeout=90)
    assert rejected.returncode!=0,rejected.stdout
    assert 'computed or setting-dependent defaults is not yet supported' in rejected.stderr,rejected.stderr
    path.write_text(SOURCE.replace('@report_zone','()=>report_zone()'))
    result=subprocess.run([compiler,'run',path,*flags],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='UTC\n'


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_literal_defaults_keep_working_in_named_handles(compiler,tmp_path,flags):
    path=tmp_path/'app.dewy'
    path.write_text("answer=(value:int64=42)=>printl(value)\nmake=()=>{\n$time.zone='UTC'\n@answer\n}\nmain=()=>{let f=make;f()}\n")
    result=subprocess.run([compiler,'run',path,*flags],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout=='42\n'


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_computed_lambda_defaults_are_rejected(compiler,tmp_path,flags):
    path=tmp_path/'app.dewy'
    path.write_text(SOURCE.replace('@report_zone',"(z:string?=get_zone)=>printl(z??'none')"))
    result=subprocess.run([compiler,'check',path,*flags],capture_output=True,text=True,timeout=90)
    assert result.returncode!=0,result.stdout
    assert 'computed or setting-dependent defaults is not yet supported' in result.stderr,result.stderr
