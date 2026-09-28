"""A deferred body cannot reuse a mutable capture's declaration-time facts."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ERRORS = [
    '''main=():>int64=>{let divisor:int64=1
read=():>int64=>42//divisor
divisor=0 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[42]
read=():>int64=>values[0]
values.clear return read()}''',
    '''main=():>int64=>{let divisor:int64=1
read=(n:int64=42//divisor):>int64=>n
divisor=0 return read()}''',
    '''Box:type=[divisor:int64]
main=():>int64=>{let box=Box[1]
read=():>int64=>42//box.divisor
box.divisor=0 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[1]
read=():>int64=>42//values[0]
values[0]=0 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[42]
let index:int64=0
read=():>int64=>values[index]
index=1 return read()}''',
    '''main=():>int64=>{let low:int64=1 let high:int64=2
read=():>int64=>{$assert low<?high return 42}
low=3 return read()}''',
    '''main=():>int64=>{let value:int64|none=1
read=():>int64=>{if value is? int64 {return 42//value} return 1}
value=0 return read()}''',
]
CASES = [
    '''outer=(values:array<int64> index:int64):>int64=>{
if index<?0 or index>=?values.length return 1
read=():>int64=>values[index]
values[index]=42 return read()}
main=():>int64=>outer([0 0] 1)''',
    '''main=():>int64=>{let original:int64=1 let snapshot=original
read=():>int64=>42//snapshot
original=0 return read()}''',
    '''main=():>int64=>{let divisor:int64=1
read=():>int64=>if divisor=?0 42 else 42//divisor
divisor=0 return read()}''',
    '''main=():>int64=>{let divisor:int64<v=>v>?0>=1
read=():>int64=>84//divisor
divisor=2 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0]
read=():>int64=>values[0]
values[0]=42 return read()}''',
    '''main=():>int64=>{let values:array<int64>=[0 0]
let index:int64=1
if index<?0 or index>=?values.length return 1
read=():>int64=>values[index]
values[1]=42 return read()}''',
    '''main=():>int64=>{let values:array<int64 length=1>=[0]
read=():>int64=>values[0]
values=[42] return read()}''',
    '''main=():>int64=>{let divisor:int64=2
read=():>int64=>84//divisor
return read()}''',
    '''main=():>int64=>{let value:int64=1
read=():>int64=>{$assert value=?1 return 42}
return read()}''',
]


@pytest.mark.parametrize('source', ERRORS)
def test_deferred_capture_cannot_reuse_stale_numeric_evidence(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


@pytest.mark.parametrize('source', CASES)
def test_stable_capture_evidence_and_contracts(tmp_path, source):
    execute(tmp_path, 'capture-facts', codegen(SrcFile(None, source), debug_locations=False))


def test_native_captured_numeric_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
