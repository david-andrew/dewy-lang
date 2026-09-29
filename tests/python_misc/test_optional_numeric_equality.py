"""Union equality uses the same numeric applicability as ordinary calls."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE='''
equal=(value:bigint?):>bool=>value=?3
unequal=(value:bigint?):>bool=>value not=?3
main=():>int64=>{
    if equal(none) or equal(0) or equal(4) return 1
    if not equal(3) or unequal(3) return 2
    if not unequal(none) or not unequal(0) or not unequal(4) return 3
    return 42
}
'''
CASES=[SOURCE, SOURCE.replace('value=?3','3=?value').replace('value not=?3','3 not=?value'),
    SOURCE.replace('=?3','=?123456789012345678901234567890').replace('equal(3)','equal(123456789012345678901234567890)'),
    SOURCE.replace('=?3','=?18446744073709551615').replace('equal(3)','equal(18446744073709551615)'),
    '''Box:type=[lower:bigint? upper:bigint?]
equal=(value:Box?):>bool=>value isnt?none and value.lower=?3 and value.upper=?8
main=():>int64=>{
    if equal(none) or equal(Box[none 8]) or equal(Box[3 none]) return 1
    return if equal(Box[3 8]) 42 else 2
}''',
    '''let calls:int64=0
left=(value:bigint?):>bigint?=>{calls=calls*10+1 return value}
right=():>int64=>{calls=calls*10+2 return 3}
main=():>int64=>{
    if left(none)=?right() or calls not=?12 return 1
    calls=0
    if left(3) not=?right() or calls not=?12 return 2
    return 42
}''']
ERRORS=['compare=(value:bigint|int64|none):>bool=>value=?3',
        'compare=(value:[number:int64]|none):>bool=>value=?3']

@pytest.mark.parametrize('source',CASES)
def test_optional_numeric_equality(tmp_path,source):
    execute(tmp_path,'optional-numeric-equality',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_optional_numeric_equality_requires_unique_numeric_alternative(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source),debug_locations=False)

def test_native_optional_numeric_equality(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
