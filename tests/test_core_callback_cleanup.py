"""Borrowed literal callbacks keep captures alive and clean up abandoned calls."""
import subprocess

import pytest

from tests.support import compiler, run_value_batch, build_exit_batch


CASES = {
    'conditional-managed': '''Callback:type=():>int64
invoke=(callback:Callback):>int64=>callback()
probe=(choose:bool):>int64=>{
 let xs:array<int64>=[42]
 let answer=if choose invoke(()=>xs[0]) else 42
 return answer
}
main=()=>{
 let before=alloc_count()
 loop i in [0..20) {
  if probe(i%2=?0) not=?42 return 1
  if alloc_count() not=?before return 2
 }
 return 42
}''',
    'abandoned-managed': '''Callback:type=():>int64
invoke=(callback:Callback n:int64):>int64=>callback()+n
probe=(stop:bool):>int64=>{
 let xs:array<int64>=[40]
 return invoke(()=>xs[0] {if stop return 42; 2})
}
main=()=>{
 let before=alloc_count()
 loop i in [0..20) {
  if probe(i%2=?0) not=?42 return 1
  if alloc_count() not=?before return 2
 }
 return 42
}''',
    'continue-managed': '''Callback:type=():>int64
invoke=(callback:Callback n:int64):>int64=>callback()+n
probe=():>int64=>{
 let total:int64=0
 loop i in [0..6) {
  let xs:array<int64>=[12]
  total+=invoke(()=>xs[0] {if i%2=?0 continue; 2})
 }
 return total
}
main=()=>{
 let before=alloc_count()
 if probe() not=?42 return 1
 return if alloc_count()=?before 42 else 2
}''',
    'forwarded-effect-order': '''Callback:type=():>int64
let trace:int64=0
invoke=(a:Callback b:Callback):>int64=>a()+b()
mark=():>void=>{trace=trace*10+1}
forward=(a:Callback b:Callback):>int64=>invoke(@a {mark(); @b})
main=()=>{
 let xs:array<int64>=[21]
 let answer=forward(()=>{trace=trace*10+2 return xs[0]} ()=>{trace=trace*10+3 return xs[0]})
 return if answer=?42 and trace=?123 42 else 1
}''',
    'literal-snapshot-before-mutation': '''Callback:type=():>int64
invoke=(a:Callback n:int64):>int64=>a()+n
main=()=>{
 let xs:array<int64>=[40]
 let answer=invoke(()=>xs[0] {xs[0]=100; 2})
 return if answer=?42 and xs[0]=?100 42 else 1
}''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_callback_cleanup(compiler, tmp_path, release, target):
    for name, (value, diagnostic) in run_value_batch(
            compiler, tmp_path, CASES, release, target).items():
        assert value == '42', f'{name}: {diagnostic or value}'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_callback_later_argument_panic(compiler, tmp_path, release, target):
    cases = {'later-panic': '''Callback:type=():>int64
invoke=(callback:Callback n:int64):>int64=>callback()+n
main=()=>{
 let xs:array<int64>=[42]
 invoke(()=>{printl"called" return xs[0]} {printl"argument"; xs[2]});
 printl"after"
}'''}
    command, failure = build_exit_batch(compiler, tmp_path, cases, release, target)
    assert command is not None, failure
    ran = subprocess.run([*command, '0'], capture_output=True, text=True, timeout=15)
    assert ran.returncode != 0, ran.stdout + ran.stderr
    assert 'argument' in ran.stdout
    assert 'called' not in ran.stdout and 'after' not in ran.stdout
