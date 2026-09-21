"""Scalar record frame placement supplies real no-allocation evidence."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/frame_record_placement.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('Point=type of [x:int64 y:int64]', 'Point:type=[x:int64 y:int64]'),
    'main=():>int64 & no_effects=>{let flags:[ok:bool n:uint8]=[true 42] flags.ok=not flags.ok return if flags.ok 1 else flags.n as int64}',
]
ERRORS = [
    'R:type=[x:int64] make=():>R & no allocates=>{let value=R[42] return value}\nmain=():>int64=>make().x',
    'R:type=[items:array<int64>] main=():>int64 & no_effects=>{let value=R[[42]] return value.items[0]}',
    # Passing a whole record still needs the separate forwarding/escape proof.
    'R:type=[x:int64] read=(value:R):>int64=>value.x\nmain=():>int64 & no allocates=>{let value=R[42] return read(value)}',
]


@pytest.mark.parametrize('source', CASES)
def test_scalar_record_frame_storage(tmp_path, source):
    execute(tmp_path, 'record-frame', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_frame_record_placement_needs_nonescape_proof(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_frame_record_placement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
