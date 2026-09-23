"""A known predicate result stays known when named, without replaying effects."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES=[
    '''$proof
ordered=(a:int64 b:int64<v=>a<=?v> c:int64<v=>b<=?v>):> <a<=?c>=>{
const result=a<=?c $assert result const opposite=not result $assert not opposite}
main=():>int64=>{ordered(1 2 3) return 42}''',
    '''main=():>int64=>{let n:int64=42 const bounded=n<?43 $assert bounded n=100 $assert bounded return 42}''',
    '''main=():>int64=>{let n:int64=42 const wrong=n>?43 $assert not wrong return 42}''',
    '''let calls:int64=0
next=():>int64<v=>v=?42>=>{calls+=1 return 42}
main=():>int64=>{const answer=next()=?42 $assert answer return if calls=?1 42 else 1}''',
]
ERRORS=[
    'f=(a:int64 b:int64):>bool=>{const answer=a<?b $assert answer return answer}',
    'main=():>int64=>{const answer=42<?41 $assert answer return 42}',
    '''change=(@n:int64):>int64=>{n=0 return 10}
main=():>int64=>{let n:int64=20 const answer=n<?change(@n) $assert answer return 42}''',
    '''let __lt__=(a:int64 b:int64):>bool=>false
main=():>int64=>{const answer=__lt__(1 2) $assert answer return 42}''',
]
@pytest.mark.parametrize('source',CASES)
def test_named_boolean_facts(tmp_path,source):
    execute(tmp_path,'boolean-value',codegen(SrcFile(None,source)))
@pytest.mark.parametrize('source',ERRORS)
def test_boolean_values_need_evidence(source):
    with pytest.raises(ReportException,match='assertion'):
        codegen(SrcFile(None,source))
def test_native_boolean_value_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
