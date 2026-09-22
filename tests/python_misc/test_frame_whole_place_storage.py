"""Frame placement uses both call lifetime and backing-storage guarantees."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    (ROOT / 'tests/fixtures/frame_whole_place_storage.dewy').read_text(),
    """flip=(@x:[ok:bool]):>void=>{x.ok=not x.ok}
main=():>int64 & no_effects=>{let box:[ok:bool]=[false] flip(@box) return if box.ok 42 else 1}""",
    """read=(@xs:array<uint8>):>int64=>{if xs.length>?0 return xs[0] as int64 return 0}
main=():>int64 & no_effects=>{let xs:array<uint8>=[42] return read(@xs)}""",
]
ERRORS = [
    # Include the whole-array handle slot in the shared frame-storage budget.
    'read=(@xs:array<int64>):>int64=>xs.length f=():>int64 & no allocates=>{let xs:array<int64>=[' + ' '.join(['42']*506) + '] return read(@xs)}',
    # A known call-only address can still replace or detach its backing storage.
    """Point=type of [x:int64]
replace=(@p:Point):>void=>{p=Point[42]}
f=():>int64 & no allocates=>{let p=Point[1] replace(@p) return p.x}""",
    """replace=(@xs:array<int64>):>void=>{xs=[42]}
f=():>int64 & no allocates=>{let xs:array<int64>=[1] replace(@xs) return xs.length}""",
    """put=(@xs:array<int64>):>void=>{if xs.length>?0 {xs[0]=42}}
f=():>int64 & no allocates=>{let xs:array<int64>=[1] put(@xs) return xs.length}""",
    # Permissions do not promise a lifetime or a known implementation.
    """f=(read:(@xs:array<int64>):>int64 & reads<xs>):>int64 & no allocates=>{
let xs:array<int64>=[42] return read(@xs)}""",
]


@pytest.mark.parametrize('source', CASES)
def test_whole_place_loans_keep_frame_storage(source, tmp_path):
    execute(tmp_path, 'whole-frame-places', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_whole_place_loans_require_stable_storage(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_frame_whole_place_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
