"""A stable element selection can carry facts; aliasing writes invalidate them."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''read=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length>):>int64=>{
const slot=i
if xs[slot]=?0 return 0
return 84//xs[slot]
}
main=():>int64=>{let xs:array<int64>=[2] return read(@xs 0)}''',
    '''read=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length>):>int64=>{
const slot=i
xs[slot]=42
$assert xs[slot]=?42
return xs[slot]
}
main=():>int64=>{let xs:array<int64>=[0] return read(@xs 0)}''',
    '''read=(@xs:array<int64 length=1>):>int64=>{
if xs[0]=?0 return 0
return 84//xs[0]
}
main=():>int64=>{let xs:array<int64 length=1>=[2] return read(@xs)}''',
]
ERRORS = [
    # A mutable selector names no stable element across a reassignment.
    '''read=(@xs:array<int64 length=2>):>int64=>{
let slot:int64=0
if xs[slot]=?0 return 0
slot=1
return 84//xs[slot]
}''',
    # A call that can write the owner invalidates its element facts too.
    '''zero=(@xs:array<int64 length=1>):>void=>{xs[0]=0}
read=(@xs:array<int64 length=1>):>int64=>{
if xs[0]=?0 return 0
zero(@xs)
return 84//xs[0]
}''',
    '''read=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length> j:int64<v=>0<=?v<?xs.length>):>int64=>{
const slot=i const other=j
if xs[slot]=?0 return 0
xs[other]=0
return 84//xs[slot]
}''',
    '''read=(@xs:array<int64> i:int64<v=>0<=?v<?xs.length>):>int64=>{
const slot=i
if xs[slot]=?0 return 0
xs.clear xs.push(0)
return 84//xs[slot]
}''',
    '''main=():>int64=>{
let xs:array<int64>=[42 0]
let i:int64=0
loop i<?xs.length {
const slot=i
if i>?0 {$assert xs[slot]=?42}
xs[slot]=42
i+=1
}
return 42
}''',
]

@pytest.mark.parametrize('source', CASES)
def test_indexed_scalar_facts(tmp_path, source):
    execute(tmp_path, 'indexed-scalar', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_indexed_scalar_facts_expire(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_indexed_scalar_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
