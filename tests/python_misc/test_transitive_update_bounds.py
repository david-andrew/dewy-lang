"""Long difference paths can prove an affine update cannot wrap."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

UPPER = '''advance=(a:int8 b:int8 c:int8 d:int8 e:int8):>int64=>{
    if a<=?b and b<=?c and c<=?d and d<=?e and e<?100 {
        a+=1
        $assert a<=?e+1
    }
    return 42
}
main=():>int64=>advance(0 1 2 3 4)
'''
LOWER = UPPER.replace('<=?', '>=?').replace('e<?100', 'e>?-100').replace('a+=1', 'a-=1').replace('e+1', 'e-1').replace('0 1 2 3 4', '4 3 2 1 0')
CASES = [UPPER, LOWER,
    UPPER.replace('a+=1', 'a=a+1'), LOWER.replace('a-=1', 'a=a-1'),
    UPPER.replace('e<?100', 'e<?127').replace('0 1 2 3 4', '123 124 125 126 126'),
    LOWER.replace('e>?-100', 'e>?-128').replace('4 3 2 1 0', '(-123) (-124) (-125) (-126) (-127)'),
]
ERRORS = [
    UPPER.replace(' and e<?100', ''),
    LOWER.replace(' and e>?-100', ''),
    UPPER.replace('a+=1', 'd=127\na+=1'),
    UPPER.replace('a+=1', 'e=127\na+=1'),
    UPPER.replace('a:int8', 'a:int64').replace('a+=1', 'a=(a as int8)+1').replace('e<?100', 'e<=?127'),
]

@pytest.mark.parametrize('source', CASES)
def test_transitive_update_bounds(tmp_path, source):
    execute(tmp_path, 'transitive-update', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_transitive_update_requires_current_nonwrapping_evidence(source):
    with pytest.raises(ReportException, match='cannot prove|outside|refinement'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_transitive_update_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
