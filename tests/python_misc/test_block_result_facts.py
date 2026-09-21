"""A block retains its result's identity only until that storage changes."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''pick=(flag:bool):>string=>if flag {let text:string='42' text text='bad'} else 'bad'
main=():>int64=>if pick(true)=?'42' 42 else 0''',
    '''pick=(flag:bool):>array<int64>=>if flag {let xs:array<int64>=[42] xs xs[0]=0} else [0]
main=():>int64=>{let xs=pick(true) return if xs.length=?1 xs[0] else 0}''',
    '''minimum=(a:int64 b:int64):>int64<v=>v<=?a and v<=?b>=>
if a<?b {let result=a result} else {let result=b result}
main=():>int64=>minimum(42 50)''',
    '''let calls:int64=0
minimum=(a:int64 b:int64):>int64<v=>v<=?a and v<=?b>=>
if a<?b {let result=a result calls+=1} else {let result=b result calls+=1}
main=():>int64=>{let answer=minimum(50 42) return if calls=?1 answer else 0}''',
]
ERRORS = [
    '''bad=(a:int64 b:int64):>int64<v=>v<=?b>=>{let answer=a answer answer=b}''',
    '''set=(@n:int64 value:int64):>void=>{n=value}
bad=(a:int64 b:int64):>int64<v=>v<=?b>=>{let answer=a answer set(@answer b)}''',
]

@pytest.mark.parametrize('source', CASES)
def test_block_result_facts(tmp_path, source):
    execute(tmp_path, 'block-result', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_block_result_identity_expires(source):
    with pytest.raises(ReportException, match='cannot prove refinement'):
        codegen(SrcFile(None, source))


def test_native_block_result_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
