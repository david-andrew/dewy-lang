"""No-allocation promises consume the same bounded placement proof as lowering."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    (ROOT / 'tests/fixtures/frame_array_storage.dewy').read_text(),
    'main=():>int64 & no_effects=>{let xs:array<int64>=[40 2] xs[0]=xs[0]+xs[1] return xs[0]}',
    'main=():>int64 & no_effects=>{let xs:array<uint32>=[40 2] return (xs[0]+xs[1]) as int64}',
    'g=():>int64=>{let xs=[42] return xs[0]} f=(x:int64=g()):>int64 & no allocates=>x main=():>int64=>f()',
    'g=():>int64=>{let xs=[42] return xs[0]} f=(x:int64):>int64 & no allocates=>if x>?0 f(x-1) else g() main=():>int64=>f(3)',
    'take=(@x:array<int64>):>int64 & reads<x>=>x.length f=():>int64 & no allocates=>{let xs:array<int64>=[42] return take(@xs)} main=():>int64=>f()+41',
]
ERRORS = [
    'f=():>array<int64> & no allocates=>{let xs=[42] return xs}',
    'f=():>int64 & no allocates=>{let xs=[42] xs.push(1) return xs[0]}',
    'f=():>int64 & no allocates=>{let xs=[42] let snapshot=xs xs[0]=1 return snapshot[0]}',
    'f=():>int64 & no allocates=>{let xs:array<int64>=[42] xs=[1] return xs[0]}',
    'f=():>int64 & no allocates=>{let xs=[42] let read=():>int64=>xs[0] return read()}',
    'f=():>int64 & no allocates=>{let xs=['+' '.join(['42']*507)+'] return xs[0]}',
    'f=():>int64 & no allocates=>{let xs=['+' '.join(['42']*300)+'] let ys=['+' '.join(['42']*300)+'] return xs[0]+ys[0]}',
]


@pytest.mark.parametrize('source', CASES)
def test_frame_arrays_execute_without_allocation(source, tmp_path):
    execute(tmp_path, 'frame-arrays', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_frame_placement_requires_nonescaping_bounded_storage(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_frame_array_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
