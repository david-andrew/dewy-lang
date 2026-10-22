"""Known-callback versions preserve eager effects, argument snapshots and panics."""
import subprocess

import pytest

from tests.support import compiler, exit_main, run_value_batch, build_exit_batch


CASES = {
    'forwarded-effects': '''Callback:type=(x:int64):>int64
let trace:int64=0
visit=(callback:Callback):>int64=>callback(1)+callback(2)
forward=(callback:Callback):>int64=>visit(@callback)
main=()=>{
 let bias:int64=10
 let answer=forward((x:int64):>int64=>{trace=trace*10+x return x+bias})
 return if answer=?23 and trace=?12 42 else 1
}''',
    'chain-effect-order': '''let trace:int64=0
main=()=>{
 let xs:array<int64>=[1 2 3]
 let ys=xs.map(x=>{trace=trace*10+x return x+3}).filter(x=>{trace=trace*10+x return x>?4})
 return if trace=?123456 and ys.length=?2 and ys[0]=?5 42 else 1
}''',
    'argument-order': '''Callback:type=():>int64
let trace:int64=0
mark=(x:int64):>int64=>{trace=trace*10+x return x}
visit=(a:int64 callback:Callback b:int64):>int64=>a+callback()+b
main=()=>{
 let bias:int64=3
 let result=visit(b=mark(2) callback=()=>{trace=trace*10+3 return bias} a=mark(1))
 return if trace=?213 and result=?6 42 else 1
}''',
    'shared-capture': '''Callback:type=():>int64
visit=(callback:Callback):>int64=>callback()+callback()
main=()=>{
 let n:int64=0
 let result=visit(($capture @n):>int64=>{n+=1 return n})
 return if n=?2 and result=?3 42 else 1
}''',
    'private-state-fallback': '''Callback:type=():>int64
visit=(callback:Callback):>int64=>callback()+callback()
main=()=>{
 let n:int64=0
 let callback=():>int64=>{n+=1 return n}
 let a=visit(@callback)
 let b=visit(@callback)
 return if a=?3 and b=?3 and callback()=?1 and n=?0 42 else 1
}''',
    'multiple-identities': '''Callback:type=(x:int64):>int64
visit=(callback:Callback):>int64=>callback(3)
main=()=>{
 let n:int64=5
 let a=visit((x:int64):>int64=>x+n)
 let b=visit((x:int64):>int64=>x*n)
 return if a=?8 and b=?15 42 else 1
}''',
}


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_callback_specialization_semantics(compiler, tmp_path, release, target):
    for name, (value, diagnostic) in run_value_batch(
            compiler, tmp_path, CASES, release, target).items():
        assert value == '42', f'{name}: {diagnostic or value}'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_callback_specialization_panics(compiler, tmp_path, release, target):
    cases = {
        'assertion': '''Callback:type=(x:int64):>int64
visit=(callback:Callback)=>{callback(1) callback(2) printl"after"}
main=()=>visit((x:int64):>int64=>{printl"before {x}" $runtime_assert x<?2 return x})''',
        'bounds': '''Callback:type=(x:int64):>int64
visit=(callback:Callback)=>{callback(0) callback(1) printl"after"}
main=()=>{
 let xs:array<int64>=[7]
 visit((x:int64):>int64=>{printl"before {x}" return xs[x]})
}''',
    }
    command, failure = build_exit_batch(compiler, tmp_path, cases, release, target)
    assert command is not None, failure
    for i, first in enumerate([1, 0]):
        ran = subprocess.run([*command, str(i)], capture_output=True, text=True, timeout=15)
        output = ran.stdout + ran.stderr
        assert ran.returncode != 0, output
        assert f'before {first}\nbefore {first + 1}\n' in output, output
        assert 'after' not in ran.stdout, output


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_callback_specialization_resolves_body(compiler, tmp_path, release):
    source = tmp_path / 'known.dewy'
    source.write_text(exit_main(CASES['multiple-identities']).replace(
        'visit=(callback:Callback):>int64=>callback(3)',
        'visit=(callback:Callback):>int64=>{let total:int64=0 '
        'loop i in [0..3) {total+=callback(i)} return total}'))
    ran = subprocess.run([compiler, 'build', source, '--ir', '-o', tmp_path / 'known',
                          *(['--release'] if release else [])],
                         capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    versions = [f for f in ran.stdout.split('fn ') if f.startswith('f_visit_') and '_callback_' in f.splitlines()[0]]
    if not versions:
        # Release can inline both specialized loops and prune their bodies.
        assert release and not any(f.startswith('f_visit_') for f in ran.stdout.split('fn ')), ran.stdout
        # Once cleanup disappears, main can also inline into its ABI wrapper.
        main = next((f for f in ran.stdout.split('fn ') if f.startswith('f_main_')), None)
        if main is None:
            main = next(f for f in ran.stdout.split('fn ') if f.startswith('__h_math_main_'))
        # Environment destruction can still use a void indirect drop helper.
        assert not any('calli ' in line and 'ty=0' in line for line in main.splitlines())
    assert all('calli ' not in f for f in versions)
