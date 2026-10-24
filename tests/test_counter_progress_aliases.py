"""Snapshots and mutable aliases do not turn geometric growth into progress."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('alias', [
    'let step=count;count+=step',
    'let a=count;let step=a;count+=step',
    'let step:int64=0;step=count;count+=step',
    'let step=():>int64=>count;count+=step()',
])
@pytest.mark.parametrize('release', [False, True])
def test_counter_alias_retains_real_obligation(compiler, tmp_path, alias, release):
    source = tmp_path / 'alias.dewy'
    source.write_text((f'''main=(args:array<string>)=>{{
let count=int64(to_int(args[1]) ?? 0)
loop i in [0..2) {{{alias}}}
printl(count)
}}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'alias'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    good = subprocess.run([binary, '7'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '28'
    bad = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout, bad.stdout + bad.stderr


@pytest.mark.parametrize('release', [False, True])
def test_later_write_to_increment_retains_check(compiler, tmp_path, release):
    source = tmp_path / 'later.dewy'
    source.write_text(('''main=(args:array<string>)=>{
let count=int64(to_int(args[1]) ?? 0)
let step:int64=0
loop i in [0..3) {count+=step;step=count}
printl(count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'later'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    good = subprocess.run([binary, '7'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '28'
    bad = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout


@pytest.mark.parametrize('via_call', [False, True])
def test_record_field_dependency_retains_check(compiler, tmp_path, via_call):
    source = tmp_path / 'fields.dewy'
    update = 'copy(@p)' if via_call else 'p.step=p.count'
    source.write_text(('''Pair:type=[count:int64 step:int64]
copy=(@p:Pair)=>{p.step=p.count}
main=(args:array<string>)=>{
let p=Pair(count=int64(to_int(args[1]) ?? 0) step=0)
loop i in [0..2) {''' + update + ''';p.count+=p.step}
printl(p.count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'fields'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    good = subprocess.run([binary, '7'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '28'
    bad = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout


def test_dynamic_index_alias_retains_check(compiler, tmp_path):
    source = tmp_path / 'indices.dewy'
    source.write_text(('''Pair:type=[count:int64 step:int64]
main=(args:array<string>)=>{
let p=[Pair(count=int64(to_int(args[1]) ?? 0) step=0)]
loop i in [0..1) {
let j=int64(to_int(args[2]) ?? 0)
p[j].step=p[i].count
p[i].count+=p[i].step
}
printl(p[0].count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'indices'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    good = subprocess.run([binary, '7', '0'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '14'
    bad = subprocess.run([binary, str(2**62), '0'], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout
