"""Direct AArch64 objects: acceptance checks (ROADMAP "Direct binary fast path").

AArch64 has no relaxation, so the direct object must match an assembler's
section for section: `llvm-mc` is the reference here (no AArch64 binutils or
emulator is assumed, so these check encoding, not execution). The Python and
native encoders must write identical objects.
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
from udewy.backend.aarch64_object import assemble

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS = REPO_ROOT / 'udewy/tests'
sys.path.insert(0, str(REPO_ROOT / 'tools'))
from compare_objects import _section_bytes, sections, symbols  # noqa: E402

PROGRAMS = ['test_comprehensive', 'test_indirect_call', 'test_short_circuit_cond', 'test_div_mod', 'test_intrinsics',
            'test_cached_operands', 'test_immediate_operands', 'test_stdlib', 'test_pending_operands', 'test_static_alloca',
            'test_register_backend_stress', 'test_mu_string']

pytestmark = pytest.mark.skipif(any(which(tool) is None for tool in ('llvm-mc', 'llvm-readelf')),
                                reason='llvm-mc is the AArch64 reference assembler for these checks')


def _asm(name: str) -> str:
    backend = get_backend('arm')
    backend.debug_info = False
    loaded = t0.load_program(TESTS / f'{name}.udewy', target_backend='arm')
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
    subprocess.run(['llvm-mc', '--triple=aarch64-linux-gnu', '-filetype=obj', str(source), '-o', str(reference)],
                   check=True)
    return reference


@pytest.mark.parametrize('name', PROGRAMS)
def test_objects_match_the_assembler(tmp_path, name):
    source = tmp_path / f'{name}.s'
    source.write_text(_asm(name))
    reference = _reference(tmp_path, source)
    direct = tmp_path / 'direct.o'
    direct.write_bytes(assemble(source.read_text()))
    expected = {key: value for key, value in _section_bytes(str(reference)).items() if key != '.note.gnu.property'}
    assert _section_bytes(str(direct)) == expected
    assert _relocations(direct) == _relocations(reference)
    assert sections(str(direct)) == {name: header for name, header in sections(str(reference)).items()
                                     if name != '.note.gnu.property'}
    # llvm-mc adds `$x`/`$d` mapping symbols for disassemblers.
    assert symbols(str(direct)) == {name: entry for name, entry in symbols(str(reference)).items()
                                    if not name.startswith('$')}


LOGICAL_IMMEDIATES = [1, 2, 3, 15, 0xFF, 0xFF00, 0x5555555555555555, 0x3333333333333333, 0x0F0F0F0F0F0F0F0F,
                      0x8000000000000000, 0x7FFFFFFFFFFFFFFF, 0xFFFFFFFF00000000, 0x00000000FFFF0000, 0xFFFFFFFFFFFFFFF0,
                      0x1111111111111111, 0xFFFE, 0xC000000000000003]


def test_logical_immediates_match_the_assembler(tmp_path):
    lines = ['.text', 'f:']
    for value in LOGICAL_IMMEDIATES:
        lines.append(f'    and x1, x2, #{value}')
        lines.append(f'    orr w3, w4, #{value & 0xFFFFFFFF}' if value & 0xFFFFFFFF not in (0, 0xFFFFFFFF) else '    nop')
        lines.append(f'    bic x5, x6, #{value}')
    source = tmp_path / 'logical.s'
    source.write_text('\n'.join(lines) + '\n')
    reference = _reference(tmp_path, source)
    assert _section_bytes_of(assemble(source.read_text()), tmp_path) == _section_bytes(str(reference))['.text']


def _section_bytes_of(data: bytes, tmp_path: Path) -> bytes:
    path = tmp_path / 'direct.o'
    path.write_bytes(data)
    return _section_bytes(str(path))['.text']


@pytest.fixture(scope='module')
def native_udewy(tmp_path_factory) -> Path:
    from native_udewy import native_udewy as build
    return build(tmp_path_factory.mktemp('native-udewy'))


@pytest.mark.parametrize('name', PROGRAMS)
def test_native_and_python_write_identical_objects(tmp_path, native_udewy, name):
    source = tmp_path / f'{name}.s'
    source.write_text(_asm(name))
    native = tmp_path / 'native.o'
    subprocess.run([native_udewy, '--assemble', str(source), str(native), '--target', 'arm'], check=True,
                   env={key: value for key, value in os.environ.items() if key != 'UDEWY_OBJECT'})
    assert native.read_bytes() == assemble(source.read_text())


RUN_PROGRAMS = PROGRAMS + ['test_alloca_spills', 'test_fib', 'test_stack_array']


@pytest.mark.skipif(any(which(tool) is None for tool in ('aarch64-linux-gnu-as', 'aarch64-linux-gnu-ld', 'qemu-aarch64')),
                    reason='running the objects needs the cross binutils and qemu-aarch64')
@pytest.mark.parametrize('name', RUN_PROGRAMS)
def test_programs_run_the_same_on_both_paths(tmp_path, monkeypatch, name):
    results = []
    for mode in ('as', 'direct'):
        monkeypatch.setenv('UDEWY_OBJECT', mode)
        backend = get_backend('arm')
        backend.debug_info = False
        loaded = t0.load_program(TESTS / f'{name}.udewy', target_backend='arm')
        code = p0.parse(t1.tokenize(loaded.source), loaded.source, backend)
        binary = backend.compile_and_link(code, name, tmp_path / mode, link_artifacts=loaded.link_artifacts)
        run = subprocess.run(['qemu-aarch64', str(binary)], capture_output=True, timeout=60)
        results.append((run.returncode, run.stdout))
    assert results[0] == results[1]
    assert results[0][0] != -11 and results[0][0] != 245   # no crash on either path
