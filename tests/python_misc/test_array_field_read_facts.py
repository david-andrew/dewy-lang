"""A field read uses current length evidence; writes use the storage contract."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute

HEADER='Box:type=[values:array<int64>]\n'
CASES=[
 '''Box:type=[values:array<int64>|bool]
main=():>int64=>{let box=Box[[20 22]]
 let kept:array<int64 length=2>=box.values
 box.values=false
 return if box.values is? bool kept[0]+kept[1] else 0}''',
 '''main=():>int64=>{let fixed:array<int64 length=2>=[20 22]
 let values:array<int64 length=2>|array<int64>=fixed
 let kept:array<int64 length=2>=values
 let grown:array<int64>=[1 2 3]
 values=grown
 return if values.length=?3 kept[0]+kept[1] else 0}''',
 HEADER+'''main=():>int64=>{let box=Box[[42]] let before:array<int64 length=1>=box.values
 box.values.clear box.values.push(99)
 return if before.length=?1 and box.values.length=?1 before[0] else 0}''',
 HEADER+'''main=():>int64=>{let box=Box[[1]] box.values.clear box.values.push(20) box.values.push(22)
 let kept:array<int64 length=2>=box.values return kept[0]+kept[1]}''',
 HEADER+'''main=():>int64=>{let box=Box[[1]] box.values=[20 22]
 let kept:array<int64 length=2>=box.values return kept[0]+kept[1]}''',
 '''$explicit_copies
let dropped:int64=0
Pack=type of [values:array<int64>
$__drop__ release=():>void=>{dropped+=values.length as int64}]
take=():>array<int64>=>{let owner=Pack[[2]] return owner.values}
main=():>int64=>{let values=take() values.push(40) return if dropped=?1 and values.length=?2 values[0]+values[1] else 0}''',
]
ERRORS=[
 HEADER+'main=():>int64=>{let box=Box[[42]] box.values.clear return box.values[0]}',
 HEADER+'clear=(@box:Box):>void=>{box.values.clear}\nmain=():>int64=>{let box=Box[[42]] clear(@box) return box.values[0]}',
 HEADER+'main=():>int64=>{let box=Box[[42]] read=():>int64=>box.values[0]\nbox.values.clear return read()}',
 HEADER+'main=():>int64=>{let box=Box[[42]] let kept:array<int64 length=1>=box.values\nkept.clear return 42}',
 'Box:type=[values:array<int64 length=1>]\nmain=():>int64=>{let box=Box[[42]] box.values.clear return 42}',
]

@pytest.mark.parametrize('source',CASES)
def test_array_field_read_facts(tmp_path,source):
 execute(tmp_path,'field-read-facts',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_array_field_facts_invalidate(source):
 with pytest.raises(ReportException):codegen(SrcFile(None,source),debug_locations=False)


def test_native_array_field_read_facts(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
