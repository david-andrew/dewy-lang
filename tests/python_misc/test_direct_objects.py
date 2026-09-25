"""Direct x86-64 objects: acceptance checks (ROADMAP "Direct binary fast path").

The direct path encodes the x86-64 backend's assembly in process and writes
the ELF object itself; `ld` still links. It must agree with `as` per symbol
(tools/compare_objects.py), link against extern objects and shared
libraries, keep `--gc-sections` and the non-executable stack working, and
produce byte-identical objects in the Python and native µDewy. Debug builds
compare with gas byte for byte once gas's jumps are forced near (`{disp32}`,
the direct path's layout): every section but `.debug_line`, whose decoded
rows must match instead, and a debugger must stop on a source line.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

from udewy import p0, t0, t1
from udewy.backend import get_backend
from udewy.backend.x86_64_object import assemble
from udewy.frontend import EntryPointOptions, entry_point
from udewy.cache import cache_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
EDGES = REPO_ROOT / 'tests/fixtures/x86_64_encoding_edges.s'
sys.path.insert(0, str(REPO_ROOT / 'tools'))
from compare_objects import _section_bytes, compare, sections  # noqa: E402

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
    from native_udewy import native_udewy as build
    return build(tmp_path_factory.mktemp('native-udewy'))


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


DEBUG_PROGRAMS = ['test_fib', 'test_comprehensive', 'test_loop', 'test_short_circuit_cond', 'test_stdlib', 'test_mu_string',
                  'test_int_calculator', 'test_static_alloca']


def _debug_asm(name: str) -> str:
    path = REPO_ROOT / 'udewy/tests' / f'{name}.udewy'
    backend = get_backend('x86_64')
    backend.debug_info = True
    loaded = t0.load_program(path, target_backend='x86_64')
    return p0.parse(t1.tokenize(loaded.source), loaded.source, backend, source_path=str(path))


def _near_reference(tmp_path: Path, text: str) -> Path:
    """gas's object with every jump forced near: the direct path's layout."""
    source = tmp_path / 'near.s'
    source.write_text(re.sub(r'^(\s+)(j[a-z]+ )', r'\1{disp32} \2', text, flags=re.M))
    reference = tmp_path / 'gas.o'
    subprocess.run(['as', str(source), '-o', str(reference)], check=True)
    return reference


def _relocations(path: Path) -> dict[str, list]:
    """Relocations per section; `.debug_line`'s without offsets (the two
    encode the same rows with different opcodes)."""
    output = subprocess.run(['readelf', '-rW', str(path)], capture_output=True, text=True, check=True).stdout
    result: dict[str, list] = {}
    current = None
    for line in output.splitlines():
        header = re.match(r"^Relocation section '\.rela(.+)' at", line)
        if header:
            current = header.group(1)
            result[current] = []
            continue
        entry = re.match(r'^([0-9a-f]+)\s+[0-9a-f]+\s+(R_\w+)\s+[0-9a-f]+\s+(\S+)\s*([+-])\s*([0-9a-f]+)$', line.strip())
        if entry and current:
            offset = None if current == '.debug_line' else int(entry.group(1), 16)
            addend = int(entry.group(5), 16) * (1 if entry.group(4) == '+' else -1)
            result[current].append((offset or 0, entry.group(2), entry.group(3), addend))
    return {name: sorted(entries) for name, entries in result.items()}


def _line_rows(path: Path) -> list[list[str]]:
    output = subprocess.run(['readelf', '--debug-dump=decodedline', str(path)], capture_output=True, text=True,
                            check=True).stdout
    return [line.split() for line in output.splitlines() if re.match(r'^\S+\s+\d+\s+0x[0-9a-f]+', line)]


def _check_debug_object(tmp_path: Path, text: str, candidate: bytes) -> None:
    reference = _near_reference(tmp_path, text)
    direct = tmp_path / 'direct.o'
    direct.write_bytes(candidate)
    skipped = {'.debug_line', '.note.gnu.property'}
    assert ({name: data for name, data in _section_bytes(str(direct)).items() if name not in skipped} ==
            {name: data for name, data in _section_bytes(str(reference)).items() if name not in skipped})
    assert _relocations(direct) == _relocations(reference)
    assert sections(str(direct)) == sections(str(reference))
    rows = _line_rows(direct)
    assert rows and rows == _line_rows(reference)


@pytest.mark.parametrize('name', DEBUG_PROGRAMS)
def test_debug_objects_match_gas_with_near_jumps(tmp_path, name):
    text = _debug_asm(name)
    assert '.loc ' in text and '.debug_info' in text
    _check_debug_object(tmp_path, text, assemble(text))


@pytest.mark.parametrize('name', DEBUG_PROGRAMS)
def test_native_and_python_write_identical_debug_objects(tmp_path, native_udewy, name):
    source = tmp_path / f'{name}.s'
    source.write_text(_debug_asm(name))
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(source), str(native)], check=True)
    assert native.read_bytes() == assemble(source.read_text())


def test_the_native_backends_debug_output_matches_gas(tmp_path, native_udewy):
    # The native x86-64 backend spells its DWARF itself; the `as` path leaves
    # that assembly in the cache.
    work = tmp_path / 'work'
    work.mkdir()
    source = work / 'program.udewy'
    source.write_text(PROGRAMS['arithmetic'])
    env = {key: value for key, value in os.environ.items() if key != 'UDEWY_OBJECT'}
    subprocess.run([native_udewy, '-c', str(source)], cwd=work, check=True, env=env)
    text = (work / '__dewycache__' / 'program.s').read_text()
    assert '.loc ' in text
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(work / '__dewycache__' / 'program.s'), str(native)], check=True)
    _check_debug_object(tmp_path, text, native.read_bytes())


@pytest.mark.skipif(which('gdb') is None, reason='gdb checks that the line table works')
@pytest.mark.parametrize('native', [False, True], ids=['python', 'native'])
def test_a_debugger_stops_on_a_source_line(tmp_path, monkeypatch, native_udewy, native):
    source = tmp_path / 'lines.udewy'
    source.write_text(PROGRAMS['arithmetic'])
    monkeypatch.chdir(tmp_path)
    if native:
        env = {**os.environ, 'UDEWY_OBJECT': 'direct'}
        subprocess.run([native_udewy, '-c', str(source)], cwd=tmp_path, check=True, env=env)
    else:
        _direct(monkeypatch, True)
        assert entry_point(source, [], EntryPointOptions(compile_only=True)) == 0
    assert not (tmp_path / '__dewycache__' / 'lines.s').exists()
    binary = tmp_path / '__dewycache__' / 'lines'
    # Line 6 is `if x % 2 =? 0 ...` inside collatz's loop.
    result = subprocess.run(['gdb', '-q', '-batch', '-ex', 'break lines.udewy:6', '-ex', 'run', '-ex', 'info line',
                             str(binary)], capture_output=True, text=True, timeout=120)
    text = result.stdout + result.stderr
    assert 'Breakpoint 1, collatz' in text and 'lines.udewy:6' in text


def _many_sections(count: int) -> str:
    lines = ['.text', '.globl _start', '_start:', '    call f0', '    movq %rax, %rdi', '    movq $60, %rax', '    syscall']
    for index in range(count):
        lines += [f'.section .text.f{index},"ax",@progbits', f'.globl f{index}', f'f{index}:', f'    movq ${index % 100}, %rax']
        if index < 3:
            lines.append(f'    call f{index + 1}')
        lines.append('    ret')
    return '\n'.join(lines + ['.section .note.GNU-stack,"",@progbits']) + '\n'


def test_more_sections_than_16_bit_indices_hold(tmp_path, native_udewy):
    # A debug build is one object: past 0xff00 sections, symbols and the
    # ELF header switch to extended numbering (SHN_XINDEX, .symtab_shndx).
    text = _many_sections(0xFF00 + 10)
    source = tmp_path / 'many.s'
    source.write_text(text)
    reference = tmp_path / 'gas.o'
    subprocess.run(['as', str(source), '-o', str(reference)], check=True)
    direct = tmp_path / 'direct.o'
    direct.write_bytes(assemble(text))
    assert ({name: data for name, data in _section_bytes(str(reference)).items() if name != '.note.gnu.property'} ==
            _section_bytes(str(direct)))
    assert sections(str(direct)) == {name: header for name, header in sections(str(reference)).items()
                                     if name != '.note.gnu.property'}
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(source), str(native)], check=True)
    assert native.read_bytes() == direct.read_bytes()
    executable = tmp_path / 'many'
    subprocess.run(['ld', '-static', '-e', '_start', '--gc-sections', str(direct), '-o', str(executable)], check=True)
    assert subprocess.run([executable]).returncode == 3
