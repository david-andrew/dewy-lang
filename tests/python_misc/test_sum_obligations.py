"""Finite sum evidence must survive snapshots, but not writes or word wrapping."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

PREFIX = 'within=(bound:int64 item:int64<v=>v<=?bound>):>int64=>42\n'
VALID = PREFIX + '''check_sum=(a:int64 b:int64 c:int64):>int64=>{
    if a<?0 or a>?100 or b<?0 or b>?100 or c<?0 or c>?b return 1
    let limit=a+b
    return within(limit a+c)
}
main=():>int64=>check_sum(20 30 22)
'''
ERRORS = [
    PREFIX + '''check_sum=(a:int64 b:int64):>int64=>{
        if a<?0 or a>?100 or b<?0 or b>?100 return 1
        let limit=a+b
        a+=1
        return within(limit a+b)
    }''',
    PREFIX + '''check_sum=(a:int64 b:int64):>int64=>{
        let limit=a+b
        if b<=?0 return 1
        return within(limit a)
    }''',
    PREFIX + '''check_sum=(a:int64 b:int64):>int64=>{
        if a<?0 or a>?100 or b<?0 or b>?100 return 1
        let limit=a+b
        limit-=1
        return within(limit a+b)
    }''',
]


def test_sum_obligations_execute(tmp_path):
    execute(tmp_path, 'sum-obligations', codegen(SrcFile(None, VALID)))


@pytest.mark.parametrize('source', ERRORS)
def test_sum_obligations_require_current_nonwrapping_evidence(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_sum_obligations(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[VALID], errors=ERRORS)
