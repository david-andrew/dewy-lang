"""The progress axiom must not prove geometric growth through control or storage."""
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('increment', [
    'let step:int64=0;loop j in [0..count) {step+=1};count+=step',
    'loop step in [0..count) {count+=step}',
])
def test_counter_control_dependency_requires_check(compiler, tmp_path, increment):
    source = tmp_path / 'control.dewy'
    source.write_text('''$runtime_checks=false
advance=(initial:int64):>int64=>{
let count=initial
loop round in [0..2) {''' + increment + '''}
return count
}
main=()=>printl(advance(10))
''')
    built = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert built.returncode != 0 and 'cannot prove exact integer result fits' in built.stderr, built.stderr


def test_inserted_counter_value_retains_check(compiler, tmp_path):
    source = tmp_path / 'insert.dewy'
    source.write_text('''main=(args:array<string>)=>{
let count=int64(to_int(args[1]) ?? 0)
let xs:array<int64>=[]
loop round in [0..2) {xs.push(count);count+=xs.pop()}
printl(count)
}
''')
    binary = tmp_path / 'insert'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    bad = subprocess.run([binary, str(2**62)], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout
