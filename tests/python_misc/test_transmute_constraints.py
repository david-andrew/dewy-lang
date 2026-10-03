"""Transmute reinterprets one plain representation (David 2026-10-02).

It cannot establish a refinement or a literal value: the same bits assigned
to such a type are proven there instead. A union's representation (a cell,
an enum word, a niche) is not its members', so transmute neither reads nor
writes one. Both compilers accept and refuse the same programs."""
import subprocess

import pytest

import test_bootstrap_lowering as native_lowering
from test_bootstrap_structural_text import build_program_driver, check_structural_text
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile

ACCEPTED = [
    # Bit reinterpretation between plain words.
    'main=():>int64=>{let x:uint64=42 return x transmute int64}',
    # Reinterpret, then let the assignment prove the refinement.
    'keep=(n:int64<n >=? 0>):>int64=>n\nmain=():>int64=>{let x:uint64=42 let raw=x transmute int64 return keep(if raw >=? 0 raw else 0)}',
]
REFUSED = [
    'main=():>int64=>{let v:int64=-1 let a=v transmute addr return 0}',
    'main=():>int64=>{let v:int64=5 let p=v transmute nat64 return 0}',
    'main=():>int64=>{let v:int64=1 let s=v transmute (-1|1) return 0}',
    'main=():>int64=>{let v:int64|none=5 let w=v transmute int64 return 0}',
    'main=():>int64=>{let v:int64=5 let w=v transmute (int64|none) return 0}',
]
REFUSAL = 'transmute cannot establish a type constraint'


def test_transmute_constraints(tmp_path):
    binary = build_program_driver(tmp_path)
    check_structural_text(binary, tmp_path, cases=ACCEPTED, errors=[])
    for index, text in enumerate(REFUSED):
        source = tmp_path / f'refused-{index}.dewy'
        source.write_text(text)
        with pytest.raises(Exception) as hosted:
            codegen(SrcFile.from_path(source), debug_locations=False)
        assert REFUSAL in str(hosted.value), (text, str(hosted.value))
        native = subprocess.run([binary, source, native_lowering.ROOT / 'library', tmp_path / 'prelude-cache'], capture_output=True, text=True, timeout=120)
        assert native.returncode == 1 and REFUSAL in native.stderr, (text, native.stderr)
