"""Closure environments preserve capture ownership across value boundaries."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


HEADER = '''drops:int64=0
copies:int64=0
Handle=type of [value:int64
    $__drop__
    release=():>void=>{drops+=1}
COPY_HOOK
]
'''
COPY_HOOK = '''    $__copy__
    duplicate=():>Handle=>{copies+=1 Handle[value+1]}
'''

CASES = {
    'move': (False, '''let owner=Handle[7]
let callback=()=>owner.value
let moved=@callback
$runtime_assert moved()=?7''', '1 0\n'),
    'copy': (True, '''let owner=Handle[7]
let callback=()=>owner.value
let copied=@callback
$runtime_assert copied()=?9 and callback()=?8 and owner.value=?7''', '3 2\n'),
    'array': (False, '''let owner=Handle[7]
let callback=()=>owner.value
let callbacks=[@callback]
$runtime_assert callbacks[0]()=?7''', '1 0\n'),
    'record': (False, '''let owner=Handle[7]
let callback=()=>owner.value
let box=[callback=@callback]
let moved=box
$runtime_assert moved.callback()=?7''', '1 0\n'),
    'copy-array': (True, '''let owner=Handle[7]
let callback=()=>owner.value
let callbacks=[@callback]
let snapshot=callbacks.copy()
$runtime_assert snapshot[0]()=?8 and callbacks[0]()=?7''', '2 1\n'),
    'copy-record': (True, '''let owner=Handle[7]
let callback=()=>owner.value
let box=[callback=@callback]
let snapshot=box.copy()
$runtime_assert snapshot.callback()=?8 and box.callback()=?7''', '2 1\n'),
    'generic': (False, '''let owner=Handle[7]
let callback=()=>owner.value
let moved=forward(@callback)
$runtime_assert moved()=?7''', '1 0\n'),
    'returned': (False, '''let callback=make(Handle[7])
$runtime_assert callback()=?7''', '1 0\n'),
    'literal-array': (False, '''let owner=Handle[7]
let callbacks=[()=>owner.value]
$runtime_assert callbacks[0]()=?7''', '1 0\n'),
    'borrow': (False, '''let owner=Handle[7]
let callback=($capture @owner)=>owner.value
$runtime_assert callback()=?7
$runtime_assert drops=?0 and owner.value=?7''', '1 0\n'),
    'borrow-write': (False, '''let owner=Handle[7]
let callback=($capture @owner)=>{owner.value+=1 return owner.value}
$runtime_assert callback()=?8
$runtime_assert drops=?0 and owner.value=?8''', '1 0\n'),
    'nested': (False, '''let owner=Handle[7]
let inner=()=>owner.value
let outer=()=>inner()
$runtime_assert outer()=?7''', '1 0\n'),
}


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('case', CASES)
def test_owner_closure(compiler, tmp_path, release, case):
    copyable, body, expected = CASES[case]
    source = tmp_path / 'closure.dewy'
    source.write_text(HEADER.replace('COPY_HOOK', COPY_HOOK if copyable else '') +
                      'forward=<T>(value:T):>T=>value\nmake=(value:Handle)=>()=>value.value\nexercise=()=>{\n' + body +
                      '\n}\nmain=()=>{exercise() printl"{drops} {copies}"}\n')
    binary = tmp_path / 'closure'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected


NEGATIVES = {
    'capture-live-owner': 'let owner=Handle[7] let callback=()=>owner.value printl"{callback()} {owner.value}"',
    'closure-live-after-transfer': 'let owner=Handle[7] let callback=()=>owner.value let moved=@callback printl"{moved()} {callback()}"',
    'explicit-copy': 'let owner=Handle[7] let callback=()=>owner.value let moved=(@callback).copy() printl"{moved()}"',
    'two-captures': 'let owner=Handle[7] let first=()=>owner.value let second=()=>owner.value printl"{first()} {second()}"',
    'generic-copy': 'let owner=Handle[7] let callback=()=>owner.value let both=duplicate(@callback) printl"{both.first()}"',
    'erased-callable': 'let owner=Handle[7] let callback=()=>owner.value let erased:<():>int64>=@callback printl"{erased()}"',
    'borrow-escape': 'let owner=Handle[7] let callback=($capture @owner)=>owner.value let escaped=[callback=@callback] printl"{escaped.callback()}"',
}


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('case', NEGATIVES)
def test_owner_closure_rejects(compiler, tmp_path, release, case):
    source = tmp_path / 'closure.dewy'
    source.write_text(HEADER.replace('COPY_HOOK', '') +
                      'duplicate=<T>(value:T):>[first:T second:T]=>[first=value second=value]\n' +
                      'main=()=>{' + NEGATIVES[case] + '}\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'closure',
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode != 0
    assert any(message in built.stderr for message in (
        'cannot copy a move-only owner', 'callable conversion would erase capture ownership',
        'borrowed owner captures require a nonescaping')), built.stderr


@pytest.mark.parametrize('release', [False, True])
def test_owner_closure_panic_cleanup(compiler, tmp_path, release):
    source = tmp_path / 'panic.dewy'
    source.write_text('''Handle=type of [value:int64
    $__drop__
    release=():>void=>{printl"drop"}
    $__copy__
    duplicate=():>Handle=>Handle[value]
]
main=()=>{
    let first=Handle[1]
    let second=Handle[2]
    let callback=()=>first.value+second.value
    let snapshot=(@callback).copy()
    $runtime_assert snapshot()=?3 and callback()=?3
    panic("done")
}
''')
    binary = tmp_path / 'panic'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 101, ran.stderr
    assert 'done' in ran.stderr
    assert ran.stdout.splitlines() == ['drop'] * 4
