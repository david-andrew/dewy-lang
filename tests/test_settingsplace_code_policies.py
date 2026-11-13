"""Same-module calls inherit code policies without changing foreign modules."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


def check(compiler,tmp_path,source,command='check'):
    p=tmp_path/'policies.dewy';p.write_text(source)
    return subprocess.run([compiler,command,p],capture_output=True,text=True,timeout=90)


@pytest.mark.parametrize('header',['','$runtime_checks=false\n'])
def test_checks_override_the_same_module_default(compiler,tmp_path,header):
    r=check(compiler,tmp_path,header+'''read=(xs:array<int64> i:int64):>int64=>xs[i]
checked=()=>{
 $runtime_checks
 printl(read([42] 0))
}
main=()=>checked()
''','run')
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\n'


def test_nested_prototype_opt_out_preserves_inherited_checks(compiler,tmp_path):
    r=check(compiler,tmp_path,'''read=(xs:array<int64> i:int64):>int64=>xs[i]
quiet=(xs:array<int64> i:int64):>int64=>{
 $prototype=false
 read(xs i)
}
checked=()=>{
 $runtime_checks
 $prototype
 printl(quiet([42] 0))
}
main=()=>checked()
''','run')
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\n'


def test_called_function_can_pin_its_own_checks(compiler,tmp_path):
    r=check(compiler,tmp_path,'''read=(xs:array<int64> i:int64):>int64=>{
 $runtime_checks
 xs[i]
}
strict=()=>{
 $runtime_checks=false
 printl(read([42] 0))
}
main=()=>strict()
''','run')
    assert r.returncode==0,r.stderr
    assert r.stdout=='42\n'


def test_foreign_module_keeps_its_own_code_policy(compiler,tmp_path):
    (tmp_path/'lib.dewy').write_text('read=(xs:array<int64> i:int64):>int64=>xs[i]\n')
    r=check(compiler,tmp_path,'''import p"lib.dewy" as lib
checked=()=>{
 $runtime_checks
 printl(lib.read([42] 0))
}
main=()=>checked()
''')
    assert r.returncode!=0
    assert 'lib.dewy:1:' in r.stderr and 'cannot prove index is in bounds' in r.stderr


def test_float_policy_reaches_a_same_module_callee(compiler,tmp_path):
    r=check(compiler,tmp_path,'''$runtime_checks
scale=(x:float64):>float64=>x*2.0
strict=()=>{
 $no_inf
 printl(scale(1e308))
}
main=()=>strict()
''','run')
    assert r.returncode==101,r.stderr+r.stdout
    assert '$no_inf' in r.stderr


def test_foreign_generic_inherits_numeric_policy(compiler,tmp_path):
    (tmp_path/'lib.dewy').write_text('scale=<T>(x:T):>T=>x*2.0\n')
    r=check(compiler,tmp_path,'''$runtime_checks
import p"lib.dewy" as lib
strict=()=>{
 $no_inf
 printl(lib.scale(1e308 as float64))
}
main=()=>strict()
''','run')
    assert r.returncode==101,r.stderr+r.stdout
    assert '$no_inf' in r.stderr,r.stderr


@pytest.mark.parametrize('flags',[(),('--release',)])
def test_generic_contexts_keep_two_callers_separate(compiler,tmp_path,flags):
    (tmp_path/'lib.dewy').write_text('scale=<T>(x:T):>T=>x*2.0\n')
    source=tmp_path/'app.dewy'
    source.write_text("""$runtime_checks
import p"lib.dewy" as lib
loose=()=>printl(lib.scale(1e308 as float64))
strict=()=>{
 $no_inf
 printl(lib.scale(1e308 as float64))
}
main=()=>{loose();strict()}
""")
    r=subprocess.run([compiler,'run',source,*flags],capture_output=True,text=True,timeout=90)
    assert r.returncode==101,r.stderr+r.stdout
    assert '$no_inf' in r.stderr,r.stderr


def test_generic_inherits_the_callers_file_header(compiler,tmp_path):
    (tmp_path/'lib.dewy').write_text('scale=<T>(x:T):>T=>x*2.0\n')
    r=check(compiler,tmp_path,"""$runtime_checks
$no_inf
import p"lib.dewy" as lib
main=()=>printl(lib.scale(1e308 as float64))
""",'run')
    assert r.returncode==101,r.stderr+r.stdout
    assert '$no_inf' in r.stderr,r.stderr


def test_generic_keeps_a_concrete_library_helpers_numerics(compiler,tmp_path):
    (tmp_path/'lib.dewy').write_text('helper=(x:float64):>bool=>x*2.0 >? x\nscale=<T>(x:T):>bool=>helper(x)\n')
    r=check(compiler,tmp_path,"""$runtime_checks
import p"lib.dewy" as lib
strict=()=>{
 $no_inf
 printl(lib.scale(1e308 as float64))
}
main=()=>strict()
""",'run')
    assert r.returncode==0,r.stderr+r.stdout
    assert r.stdout=='true\n'
    assert '`helper` is not compiled under `$no_inf`' in r.stderr,r.stderr


def test_function_parameter_keeps_declared_code_and_warns(compiler,tmp_path):
    r=check(compiler,tmp_path,"""$runtime_checks
wide=(x:float64):>bool=>x*2.0 >? x
apply=(f:<(x:float64):>bool>):>bool=>{
 $no_inf
 f(1e308)
}
main=()=>printl(apply(@wide))
""",'run')
    assert r.returncode==0,r.stderr
    assert r.stdout=='true\n'
    assert '`f` is a function parameter' in r.stderr and '$no_inf' in r.stderr,r.stderr


def test_generic_origin_survives_an_unchanged_entry_vector(compiler,tmp_path):
    (tmp_path/'lib.dewy').write_text("""$runtime_checks
helper=(x:float64):>bool=>x*2.0 >? x
run=<T>(x:T):>bool=>{
 $no_inf
 helper(x)
}
""")
    r=check(compiler,tmp_path,"""$runtime_checks
import p"lib.dewy" as lib
main=()=>printl(lib.run(1e308 as float64))
""",'run')
    assert r.returncode==0,r.stderr+r.stdout
    assert r.stdout=='true\n'
    assert '`helper` is not compiled under `$no_inf`' in r.stderr,r.stderr
