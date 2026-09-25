"""Direct RISC-V objects: acceptance checks (ROADMAP "Direct binary fast path").

The direct path writes the long form (no compressed instructions, no
R_RISCV_RELAX), so it must match `llvm-mc -mattr=+m,+f,+d,-relax,-c` section
for section (no RISC-V binutils or emulator is assumed, so these check
encoding, not execution). `li` must pick RISCVMatInt's sequence for every
constant. The Python and native encoders must write identical objects.
"""
from __future__ import annotations

import os
import random
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

import pytest

from udewy import p0, t0, t1
from udewy.backend import get_backend
from udewy.backend.riscv_object import assemble

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / 'udewy/tests'
EDGES = REPO_ROOT / 'tests/fixtures/riscv64_encoding_edges.s'
sys.path.insert(0, str(REPO_ROOT / 'tools'))
from compare_objects import _section_bytes, sections, symbols  # noqa: E402

PROGRAMS = ['test_comprehensive', 'test_fib', 'test_short_circuit_cond', 'test_div_mod', 'test_intrinsics',
            'test_cached_operands', 'test_immediate_operands', 'test_stdlib', 'test_pending_operands', 'test_static_alloca',
            'test_local_registers', 'test_mu_string', 'test_int_calculator']

pytestmark = pytest.mark.skipif(any(which(tool) is None for tool in ('llvm-mc', 'llvm-readelf')),
                                reason='llvm-mc is the RISC-V reference assembler for these checks')


def _asm(name: str) -> str:
    backend = get_backend('riscv')
    backend.debug_info = False
    loaded = t0.load_program(TESTS / f'{name}.udewy', target_backend='riscv')
    return p0.parse(t1.tokenize(loaded.source), loaded.source, backend)


def _relocations(path: Path) -> dict[str, list]:
    out = subprocess.run(['llvm-readelf', '-rW', str(path)], capture_output=True, text=True, check=True).stdout
    result: dict[str, list] = {}
    current = None
    for line in out.splitlines():
        header = re.match(r"^Relocation section '\.rela(.+)' at", line)
        if header:
            current = header.group(1)
            result[current] = []
            continue
        entry = re.match(r'^([0-9a-f]+)\s+[0-9a-f]+\s+(R_\w+)\s+[0-9a-f]+\s+(\S+)\s*([+-])\s*([0-9a-f]+)$', line.strip())
        if entry and current:
            sign = 1 if entry.group(4) == '+' else -1
            result[current].append((int(entry.group(1), 16), entry.group(2), entry.group(3), sign * int(entry.group(5), 16)))
    return {name: sorted(entries) for name, entries in result.items()}


def _reference(tmp_path: Path, source: Path) -> Path:
    reference = tmp_path / 'reference.o'
    subprocess.run(['llvm-mc', '--triple=riscv64-linux-gnu', '-mattr=+m,+f,+d,-relax,-c', '-filetype=obj', str(source),
                    '-o', str(reference)], check=True)
    return reference


def _check(tmp_path: Path, source: Path) -> None:
    reference = _reference(tmp_path, source)
    direct = tmp_path / 'direct.o'
    direct.write_bytes(assemble(source.read_text()))
    # llvm-mc creates .data only when it is used; empty sections are no difference.
    assert ({name: data for name, data in _section_bytes(str(direct)).items() if data} ==
            {name: data for name, data in _section_bytes(str(reference)).items() if data})
    assert _relocations(direct) == _relocations(reference)
    # llvm-mc word-aligns `.text` but leaves `.section`-made code sections
    # byte-aligned; the direct path word-aligns every code section.
    expected = {name: (kind, flags, max(align, 4) if 'X' in flags else align, size)
                for name, (kind, flags, align, size) in sections(str(reference)).items()}
    assert sections(str(direct)) == expected
    # llvm-mc adds `$x`/`$d` mapping symbols for disassemblers.
    assert symbols(str(direct)) == {name: entry for name, entry in symbols(str(reference)).items()
                                    if not name.startswith('$')}


@pytest.mark.parametrize('name', PROGRAMS)
def test_objects_match_the_assembler(tmp_path, name):
    source = tmp_path / f'{name}.s'
    source.write_text(_asm(name))
    _check(tmp_path, source)


def test_encoding_edges_match_the_assembler(tmp_path):
    _check(tmp_path, EDGES)


def _constants() -> list[int]:
    generator = random.Random(7)
    values = set()
    for bit in range(64):
        for delta in (-1, 0, 1):
            values.update({(1 << bit) + delta, -(1 << bit) + delta, (1 << bit) - 1, ~((1 << bit) - 1)})
    for _ in range(300):
        values.add(generator.getrandbits(64) - (1 << 63))
        values.add(generator.getrandbits(generator.randint(1, 63)))
        values.add(-generator.getrandbits(generator.randint(1, 63)))
        shifted = generator.getrandbits(20) << generator.randint(0, 44)
        values.update({shifted | generator.getrandbits(12), shifted | 0x7FF, shifted | 0x17FF})
    return sorted({(value + (1 << 63)) % (1 << 64) - (1 << 63) for value in values})


def test_li_matches_the_assembler(tmp_path):
    source = tmp_path / 'li.s'
    source.write_text('.text\n' + ''.join(f'    li a0, {value}\n' for value in _constants()))
    _check(tmp_path, source)


@pytest.fixture(scope='module')
def native_udewy(tmp_path_factory) -> Path:
    from native_udewy import native_udewy as build
    return build(tmp_path_factory.mktemp('native-udewy'))


def _native(native_udewy: Path, tmp_path: Path, source: Path) -> bytes:
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(source), str(native), '--target', 'riscv'], check=True,
                   env={key: value for key, value in os.environ.items() if key != 'UDEWY_OBJECT'})
    return native.read_bytes()


@pytest.mark.parametrize('name', PROGRAMS)
def test_native_and_python_write_identical_objects(tmp_path, native_udewy, name):
    source = tmp_path / f'{name}.s'
    source.write_text(_asm(name))
    assert _native(native_udewy, tmp_path, source) == assemble(source.read_text())


def test_native_and_python_agree_on_edges_and_li(tmp_path, native_udewy):
    assert _native(native_udewy, tmp_path, EDGES) == assemble(EDGES.read_text())
    source = tmp_path / 'li.s'
    source.write_text('.text\n' + ''.join(f'    li a0, {value}\n' for value in _constants()))
    assert _native(native_udewy, tmp_path, source) == assemble(source.read_text())
