"""Opt-in executable tests for the pinned performance-core experiment.

DEWY_SLOPPY_EMITTER selects the built emitter; DEWY_TEST_DRIVER_COMPILER
selects the independently certified Dewy compiler for source acceptance tests.
"""
import os
import subprocess
from pathlib import Path

import pytest

from tools.sloppy_bridge.adapter import Adapter
from tools.sloppy_bridge.run import compile_program
from udewy import p0, t1
from udewy.backend.x86_64 import X86_64Backend
from udewy.stream import Recorder, Stream

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def emitter():
    path = os.environ.get('DEWY_SLOPPY_EMITTER')
    if not path: pytest.skip('set DEWY_SLOPPY_EMITTER for the compiler-core experiment')
    return Path(path).resolve(strict=True)


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_TEST_DRIVER_COMPILER')
    if not path: pytest.skip('set DEWY_TEST_DRIVER_COMPILER for source checks')
    return Path(path).resolve(strict=True)


def stream_of(source):
    recorder = Recorder(X86_64Backend(), [])
    p0.parse(t1.tokenize(source), source, recorder)
    return recorder.stream()


def execute(stream, emitter, tmp_path, mode):
    ir = tmp_path / 'program.ir'
    ir.write_bytes(Stream(stream).play(Adapter()))
    binary = tmp_path / 'program'
    subprocess.run([emitter, ir, binary, mode], check=True, capture_output=True, timeout=30)
    return subprocess.run([binary], capture_output=True, timeout=10, check=False)


@pytest.mark.parametrize('mode', ['debug', 'release'])
@pytest.mark.parametrize('name', ['test_address_displacements', 'test_intrinsic_operands'])
def test_existing_backend_abi_cases(emitter, tmp_path, mode, name):
    source = (ROOT / f'udewy/tests/{name}.udewy').read_text()
    run = execute(stream_of(source), emitter, tmp_path, mode)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)


EDGE_CASES = {
    'division': '''
let check=(x:int y:int):>int=>{
    if x // y not=? -1 or x % y not=? x {return 1}
    if __unsigned_idiv__(x y) not=? -1 or __unsigned_mod__(x y) not=? x {return 2}
    return 0
}
let overflow=(x:int y:int):>int=>{
    if x // y not=? x or x % y not=? 0 {return 3}
    return 0
}
let negative=(x:int y:int):>int=>{
    if x // y not=? -2 or x % y not=? -1 {return 4}
    return 0
}
let main=():>int=>{return check(123 0) + overflow(-9223372036854775808 (-1)) + negative(-7 3)}
''',
    'booleans-shifts': '''
let check=(x:int y:int):>int=>{
    if (x <? y) not=? -1 or (x >? y) not=? 0 {return 1}
    if (not (x <? y)) not=? 0 {return 2}
    if __unsigned_lt__(x y) not=? 0 or __unsigned_gte__(x y) not=? -1 {return 3}
    if __signed_shr__(x 65) not=? -4 or (x >> 65) not=? 9223372036854775804 {return 4}
    return 0
}
let main=():>int=>{return check(-8 3)}
''',
    'allocation-lifetime': '''
let sum8=(a:int b:int c:int d:int e:int f:int g:int h:int):>int=>{return a+b+c+d+e+f+g+h}
let check=(size:int):>int=>{
    let pointers:int=__alloca__(32)
    let i:int=0
    loop i <? 4 {
        let p:int=__alloca__(size+i)
        __store__(i+40 p)
        __store__(p pointers+i*8)
        if sum8(1 2 3 4 5 6 7 __load__(p)) not=? i+68 {return 1}
        i+=1
    }
    i=0
    loop i <? 4 {
        if __load__(__load__(pointers+i*8)) not=? i+40 {return 2}
        i+=1
    }
    return 0
}
let main=():>int=>{return check(8)}
''',
    'lazy-control': '''
let touched:int=0
let touch=():>int=>{touched+=1 return -1}
let main=():>int=>{
    let i:int=0
    let total:int=0
    loop i <? 20 {
        i+=1
        if i =? 2 or i =? 3 {continue}
        if i >? 10 {break}
        total+=i
    }
    if 0 and touch() {return 1}
    if -1 or touch() {total+=1}
    if touched not=? 0 or total not=? 51 {return 2}
    return 0
}
''',
    'static-relocations': '''
let add=(x:int):>int=>{return x+2}
const table:int=__static_words__(add "hi" 40)
let main=():>int=>{
    let f:int=__load__(table)
    let s:int=__load__(table+8)
    if __load__(s-8) not=? 2 or __load_u8__(s) not=? 104 {return 1}
    if (@f)(__load__(table+16)) not=? 42 {return 2}
    return 0
}
''',
}


@pytest.mark.parametrize('mode', ['debug', 'release'])
@pytest.mark.parametrize('name', EDGE_CASES)
def test_word_abi_and_control(emitter, tmp_path, mode, name):
    run = execute(stream_of(EDGE_CASES[name]), emitter, tmp_path, mode)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)


DEWY_CASES = {
    'records-copy-growth': '''
Particle:type=[x:int64 y:int64]
main=():>int64=>{
    let xs:array<Particle>=[Particle[20 22]]
    let copy=xs.copy
    let saved=xs[0]
    loop i in 0..100 {xs.push(Particle[i i])}
    $runtime_assert xs.length >? 0
    xs[0].x=99
    $runtime_assert copy.length >? 0
    if copy[0].x not=? 20 or saved.x not=? 20 return 1
    return copy[0].x+saved.y
}
''',
    'family-snapshot': (ROOT / 'dewy/audits/2026-09-30/cases/representation/family_array_snapshot.dewy').read_text(),
    'lazy-functions': '''
let counter:int64=0
bump=():>bool=>{counter+=1 return true}
main=():>int64=>{
    if false and bump() return 1
    if true or bump() {counter+=42}
    return counter
}
''',
}


@pytest.mark.parametrize('name', DEWY_CASES)
def test_checked_source_behavior(emitter, compiler, tmp_path, name):
    source = tmp_path / f'{name}.dewy'
    source.write_text(DEWY_CASES[name])
    binary, _ = compile_program(source, compiler, emitter, tmp_path, release=True)
    result = subprocess.run([binary], capture_output=True, timeout=10, check=False)
    assert result.returncode == 42, (result.returncode, result.stdout, result.stderr)


@pytest.mark.parametrize('body,diagnostic', [
    ('main=():>int64=>{let xs:array<int64>=[42] return xs[1]}', 'bounds'),
    ('read=(xs:array<int64> i:addr):>int64=>xs[i]\nmain=():>int64=>42', 'bounds'),
    ('''main=():>int64=>{
    let xs:array<int64>=[42]
    let index=xs.length-1
    xs=[]
    return xs[index]
}''', 'bounds'),
])
def test_source_obligations_reject_before_codegen(emitter, compiler, tmp_path, body, diagnostic):
    source = tmp_path / 'rejected.dewy'
    source.write_text(body)
    with pytest.raises(RuntimeError, match=diagnostic):
        compile_program(source, compiler, emitter, tmp_path, release=True)
    assert not (tmp_path / 'program.ir').exists()
    assert not (tmp_path / 'program').exists()


def test_wrong_target_is_rejected():
    data = stream_of('let main=():>int=>{return 42}')
    adapter = Adapter()
    adapter.bytecode_target = 'wasm32'
    with pytest.raises(ValueError, match='target mismatch'):
        Stream(data).play(adapter)


def test_unsupported_intrinsics_and_externals_are_explicit():
    adapter = Adapter()
    label = adapter.declare_function('main', 0)
    adapter.begin_function(label, 'main', 0, True)
    with pytest.raises(ValueError, match='unsupported'):
        adapter.emit_intrinsic('__breakpoint__', 0)
    with pytest.raises(ValueError, match='external function'):
        adapter.declare_extern_function('malloc', 1)
