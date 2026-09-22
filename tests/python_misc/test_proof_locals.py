"""Erased proofs may name intermediate scalar facts without hiding evaluation."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    "main=():>int64=>{const yes=true const answer=false $assert yes $assert not answer return 42}",
    '''$proof
ordered=(a:int64 b:int64<v=>a<=?v> c:int64<v=>b<=?v>):> <a<=?c>=>{
const middle=b $assert a<=?middle $assert middle<=?c}
main=():>int64=>{ordered(1 2 3) return 42}''',
    '''$proof
nonempty=(xs:array<int64 length>?0>):> <xs.length>?0>=>{
const count=xs.length $assert count>?0}
main=():>int64=>{let xs=[42] nonempty(xs) return 42}''',
    '''$proof
positive=(n:int64<v=>v>?0>):> <n>?0>=>{
const zero=0 if n>?zero {const answer=true $assert answer} else {}}
main=():>int64=>{positive(42) return 42}''',
]
ERRORS = [
    "main=():>int64=>{const answer=false $assert answer return 42}",
    "main=():>int64=>{let yes=true yes=false $assert yes return 42}",
    '''effect=():>int64=>{printl('effect') return 42}
$proof
bad=(n:int64):> <n=?n>=>{const x=effect()}''',
    '''let global:int64=42
$proof
bad=(n:int64):> <n=?n>=>{const x=global}''',
    '''$proof
bad=(n:int64):> <n>?0>=>{const x=n $assert x>?0}''',
    '''$proof
bad=(n:int64):> <n=?n>=>{let x=n x+=1}''',
    '''$proof
bad=(xs:array<int64>):> <xs.length=?xs.length>=>{const alias=xs}''',
]

@pytest.mark.parametrize('source',CASES)
def test_proof_locals(tmp_path,source):
    output=codegen(SrcFile(None,source))
    execute(tmp_path,'proof-locals',output)

@pytest.mark.parametrize('source',ERRORS)
def test_proof_locals_keep_erasure_boundary(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_proof_locals(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
