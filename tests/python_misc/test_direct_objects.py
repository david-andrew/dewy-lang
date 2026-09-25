"""Direct x86-64 objects: acceptance checks (ROADMAP "Direct binary fast path").

The direct path encodes the x86-64 backend's assembly in process and writes
the ELF object itself; `ld` still links. It must agree with `as` per symbol
(tools/compare_objects.py), link against extern objects and shared
libraries, keep `--gc-sections` and the non-executable stack working, and
produce byte-identical objects in the Python and native µDewy.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

from udewy import p0, t1
from udewy.backend import get_backend
from udewy.backend.x86_64_object import assemble
from udewy.frontend import EntryPointOptions, entry_point
from udewy.cache import cache_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
EDGES = REPO_ROOT / 'tests/fixtures/x86_64_encoding_edges.s'
sys.path.insert(0, str(REPO_ROOT / 'tools'))
from compare_objects import compare  # noqa: E402

pytestmark = pytest.mark.skipif(
    any(which(tool) is None for tool in ('as', 'ld', 'objdump', 'readelf', 'cc')),
    reason='binutils and a C compiler are needed to check direct objects against them')

PROGRAMS = {
    'arithmetic': '''
let collatz = (n:int):>int => {
    let steps:int = 0
    let x:int = n
    loop x not=? 1 {
        if x % 2 =? 0 { x = x // 2 } else { x = x * 3 + 1 }
        steps = steps + 1
    }
    return steps
}
let main = ():>int => {
    let total:int = 0
    let i:int = 1
    loop i <? 200 { total = total + collatz(i)  i = i + 1 }
    if total not=? 8392 { return 1 }
    if (0 - 7) // 2 not=? (0 - 3) { return 2 }
    if __signed_shr__(0 - 64 3) not=? (0 - 8) { return 3 }
    return 42
}
''',
    'memory': '''
const words:int = __static_words__(3 5 8)
let counter:int = 0
let bump = (by:int):>int => {
    counter = counter + by
    return counter
}
let main = ():>int => {
    let buffer:int = __alloca__(64)
    let i:int = 0
    loop i <? 8 { __store__(i * i buffer + i * 8)  i = i + 1 }
    let sum:int = 0
    i = 0
    loop i <? 8 { sum = sum + __load__(buffer + i * 8)  i = i + 1 }
    __store_u8__(200 buffer)
    if __load_u8__(buffer) not=? 200 { return 1 }
    if __load_i8__(buffer) not=? (0 - 56) { return 2 }
    let f:int = @bump
    (@f)(5)
    if bump(1) not=? 6 { return 3 }
    return sum + __load__(words + 16) - 140 + 42 - 8
}
''',
    'output': '''
let say = (text:int):>void => {
    __syscall3__(1 1 text __load__(text - 8))
    __syscall3__(1 1 "\\n" 1)
    return void
}
let main = ():>int => {
    let i:int = 1
    loop i <=? 15 {
        if i % 15 =? 0 { say("FizzBuzz") }
        else if i % 3 =? 0 { say("Fizz") }
        else if i % 5 =? 0 { say("Buzz") }
        else { say("-") }
        i = i + 1
    }
    return 42
}
''',
}


def _direct(monkeypatch, enabled: bool) -> None:
    if enabled:
        monkeypatch.setenv('UDEWY_OBJECT', 'direct')
    else:
        monkeypatch.delenv('UDEWY_OBJECT', raising=False)


def test_encoding_edges_agree_with_gas(tmp_path):
    reference = tmp_path / 'gas.o'
    subprocess.run(['as', str(EDGES), '-o', str(reference)], check=True)
    candidate = tmp_path / 'direct.o'
    candidate.write_bytes(assemble(EDGES.read_text()))
    assert compare(str(reference), str(candidate)) == []


def test_the_comparator_notices_a_changed_instruction(tmp_path):
    reference = tmp_path / 'gas.o'
    subprocess.run(['as', str(EDGES), '-o', str(reference)], check=True)
    candidate = tmp_path / 'flipped.o'
    data = bytearray(assemble(EDGES.read_text()))
    candidate.write_bytes(data)
    # Flip a register bit in the first instruction of `moves`
    # (`movq %rax, %rbx`: 48 89 c3 becomes 48 89 c2, `movq %rax, %rdx`).
    headers = subprocess.run(['readelf', '-SW', str(candidate)], capture_output=True, text=True).stdout
    match = re.search(r'\.text\.moves\s+PROGBITS\s+[0-9a-f]+\s+([0-9a-f]+)', headers)
    data[int(match.group(1), 16) + 2] ^= 0x01
    candidate.write_bytes(data)
    assert compare(str(reference), str(candidate)) != []


def test_objects_are_deterministic():
    text = EDGES.read_text()
    assert assemble(text) == assemble(text)


@pytest.mark.parametrize('name', sorted(PROGRAMS))
def test_programs_behave_the_same_on_both_paths(tmp_path, monkeypatch, name):
    results = []
    for enabled in (False, True):
        _direct(monkeypatch, enabled)
        work = tmp_path / ('direct' if enabled else 'as')
        work.mkdir()
        source = work / f'{name}.udewy'
        source.write_text(PROGRAMS[name])
        assert entry_point(source, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
        run = subprocess.run([cache_artifact(source).resolve()], capture_output=True, timeout=30)
        results.append((run.returncode, run.stdout, run.stderr))
    assert results[0] == results[1]
    assert results[0][0] == 42


def _parse(source: str):
    backend = get_backend('x86_64')
    backend.debug_info = False
    return backend, p0.parse(t1.tokenize(source), source, backend)


def test_extern_object_links_and_runs(tmp_path, monkeypatch):
    externs = tmp_path / 'externs.c'
    externs.write_text('long ext_value = 7;\nlong triple(long x) { return x * 3; }\n')
    subprocess.run(['cc', '-c', str(externs), '-o', str(tmp_path / 'c_externs.o')], check=True)
    source = 'let triple = (x:int):>int => extern\nlet ext_value:int = extern\nlet main = ():>int => { return triple(ext_value) }\n'
    _direct(monkeypatch, True)
    backend, code = _parse(source)
    output = backend.compile_and_link(code, 'externs', tmp_path, link_artifacts=[str(tmp_path / 'c_externs.o')])
    assert not (tmp_path / 'externs.s').exists()
    assert subprocess.run([output]).returncode == 21


def test_shared_library_links_through_the_plt(tmp_path, monkeypatch):
    library = tmp_path / 'libdouble.so'
    (tmp_path / 'double.c').write_text('long twice(long x) { return 2 * x; }\n')
    subprocess.run(['cc', '-shared', '-fPIC', str(tmp_path / 'double.c'), '-o', str(library)], check=True)
    source = 'let twice = (x:int):>int => extern\nlet main = ():>int => { return twice(21) }\n'
    _direct(monkeypatch, True)
    backend, code = _parse(source)
    output = backend.compile_and_link(code, 'shared', tmp_path, link_artifacts=[str(library)])
    relocations = subprocess.run(['readelf', '-rW', str(tmp_path / 'shared.o')], capture_output=True, text=True).stdout
    assert 'R_X86_64_PLT32' in relocations and 'twice' in relocations
    run = subprocess.run([output], env={**os.environ, 'LD_LIBRARY_PATH': str(tmp_path)})
    assert run.returncode == 42


def test_an_undefined_symbol_fails_the_link_the_same_way(tmp_path, monkeypatch, capfd):
    source = 'let missing = (x:int):>int => extern\nlet main = ():>int => { return missing(1) }\n'
    messages = []
    for enabled in (False, True):
        _direct(monkeypatch, enabled)
        work = tmp_path / ('direct' if enabled else 'as')
        work.mkdir()
        backend, code = _parse(source)
        with pytest.raises(subprocess.CalledProcessError) as failure:
            backend.compile_and_link(code, 'undefined', work)
        assert failure.value.cmd[0] == 'ld'
        messages.append('undefined reference to `missing' in capfd.readouterr().err)
    assert messages == [True, True]


def test_gc_sections_drops_an_unreferenced_function(tmp_path):
    text = EDGES.read_text() + '''
.section .text.never_called,"ax",@progbits
.globl never_called
never_called:
    ret
'''
    objects = tmp_path / 'edges.o'
    objects.write_bytes(assemble(text))
    support = tmp_path / 'support.s'
    support.write_text('.globl external_function\n.globl external_data\n.text\nexternal_function:\n    ret\n'
                       '.data\nexternal_data:\n    .quad 0\n.section .note.GNU-stack,"",@progbits\n')
    subprocess.run(['as', str(support), '-o', str(tmp_path / 'support.o')], check=True)
    executable = tmp_path / 'edges'
    subprocess.run(['ld', '-static', '-e', '_start', '--gc-sections', str(objects), str(tmp_path / 'support.o'),
                    '-o', str(executable)], check=True)
    symbols = subprocess.run(['nm', str(executable)], capture_output=True, text=True).stdout
    names = {line.split()[-1] for line in symbols.splitlines()}
    assert 'never_called' not in names and '__main__' in names
    # A section flagged `R` (SHF_GNU_RETAIN) survives even unreferenced.
    assert '.global1' in names
    # The GNU-stack note keeps the stack non-executable.
    segments = subprocess.run(['readelf', '-lW', str(executable)], capture_output=True, text=True).stdout
    stack = next(line for line in segments.splitlines() if 'GNU_STACK' in line)
    assert stack.split()[-2] == 'RW'


@pytest.fixture(scope='module')
def native_udewy(tmp_path_factory) -> Path:
    """The native µDewy compiler built by the Python one."""
    work = tmp_path_factory.mktemp('native-udewy')
    main = REPO_ROOT / 'udewy/bootstrap/main.udewy'
    subprocess.run([sys.executable, '-m', 'udewy', '--no-debug-info', '-c', str(main)], cwd=work, check=True,
                   env={**os.environ, 'PYTHONPATH': str(REPO_ROOT)})
    return work / cache_artifact(main, cwd=work)


def test_native_and_python_write_identical_objects(tmp_path, native_udewy):
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(EDGES), str(native)], check=True)
    assert native.read_bytes() == assemble(EDGES.read_text())


@pytest.mark.parametrize('name', sorted(PROGRAMS))
def test_native_direct_path_matches_the_assembler_path(tmp_path, native_udewy, name):
    results = []
    for mode in ('as', 'direct'):
        work = tmp_path / mode
        work.mkdir()
        source = work / f'{name}.udewy'
        source.write_text(PROGRAMS[name])
        env = {key: value for key, value in os.environ.items() if key != 'UDEWY_OBJECT'}
        if mode == 'direct':
            env['UDEWY_OBJECT'] = 'direct'
        subprocess.run([native_udewy, '--no-debug-info', '-c', str(source)], cwd=work, check=True, env=env)
        binary = work / '__dewycache__' / name
        run = subprocess.run([binary], capture_output=True, timeout=30)
        results.append((run.returncode, run.stdout, run.stderr))
        if mode == 'direct':
            assert not (work / '__dewycache__' / f'{name}.s').exists()
    assert results[0] == results[1]
    assert results[0][0] == 42
