"""A borrowed scalar address must not force bounded local storage to escape."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    (ROOT / 'tests/fixtures/frame_place_storage.dewy').read_text(),
    '''put=(@x:uint8):>void=>{x=42}
main=():>int64 & no_effects=>{let xs:array<uint8>=[0] put(@xs[0]) return xs[0] as int64}''',
    '''flip=(@x:bool):>void=>{x=not x}
main=():>int64 & no_effects=>{let box:[ok:bool]=[false] flip(@box.ok) return if box.ok 42 else 1}''',
]
ERRORS = [
    # A public permission describes behavior, not the address lifetime.
    '''f=(callback:(@x:int64):>void & mutates<x>):>int64 & no allocates=>{
let xs:array<int64>=[0] callback(@xs[0]) return xs[0]}''',
    '''forward=(callback:(@x:int64):>void & mutates<x> @x:int64):>void=>callback(@x)
f=(callback:(@x:int64):>void & mutates<x>):>int64 & no allocates=>{
let xs:array<int64>=[0] forward(@callback @xs[0]) return xs[0]}''',
    # Whole-owner mutation may replace or grow its storage.
    '''grow=(@xs:array<int64>):>void=>xs.push(1)
f=():>int64 & no allocates=>{let xs:array<int64>=[42] grow(@xs) return xs.length}''',
]


@pytest.mark.parametrize('source', CASES)
def test_scalar_place_borrows_reuse_frame_storage(source, tmp_path):
    execute(tmp_path, 'frame-places', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_unknown_or_whole_owner_places_keep_storage_obligations(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_frame_place_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
