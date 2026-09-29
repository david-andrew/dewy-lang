"""Local place lifetimes resolve imported helper bodies before classifying calls."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]
PREFIX=f'import p"{ROOT / "tests/fixtures/imported_place_helpers.dewy"}" as helpers\n'
BODIES=[
    """main=():>int64=>{let table:dict<string int64>=[]
helpers.fill(@table)
$runtime_assert 'x' in? table
let entry=@table['x'] entry+=2 return entry}""",
    """forward=(@table:dict<string int64>):>int64=>{
helpers.fill(@table)
$runtime_assert 'x' in? table
let entry=@table['x'] entry+=2 return entry}
main=():>int64=>{let table:dict<string int64>=[] return forward(@table)}""",
    """main=():>int64=>{let table:dict<string int64>=[]
helpers.fill(@table)
$runtime_assert 'x' in? table
let entry=@table['x'] entry+=2
let answer=entry helpers.relay(@table) return answer}""",
]
BAD_BODIES=[
    """main=():>int64=>{let table:dict<string int64>=['x'->40]
let entry=@table['x'] helpers.clear(@table) entry+=2 return entry}""",
    """main=():>int64=>{let table:dict<string int64>=['x'->40]
let entry=@table['x'] helpers.relay(@table) entry+=2 return entry}""",
    """forward=(@table:dict<string int64> callback:(@table:dict<string int64>):>void):>int64=>{
if 'x' in? table {let entry=@table['x'] callback(@table) entry+=2 return entry} return 1}""",
]
CASES=[PREFIX+body for body in BODIES]
ERRORS=[PREFIX+body for body in BAD_BODIES]

@pytest.mark.parametrize('source',CASES)
def test_imported_calls_do_not_expose_unrelated_future_places(tmp_path,source):
    path=tmp_path/'imported-place.dewy';path.write_text(source)
    execute(tmp_path,'imported-place',codegen(SrcFile.from_path(path),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_imported_writes_and_unknown_callbacks_still_fence_places(tmp_path,source):
    path=tmp_path/'bad-place.dewy';path.write_text(source)
    with pytest.raises(ReportException,match='place.*(lifetime|conflicts)'):
        codegen(SrcFile.from_path(path),debug_locations=False)

def test_native_imported_local_places(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
