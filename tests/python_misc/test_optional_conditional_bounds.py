"""Optional joins keep common payload bounds without proving presence."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = """read=(value:addr):>int64=>value
get=(flag:bool):>addr?=>if flag 42 as addr else none
work=(flag:bool value:addr):>int64=>{
    let target=if flag value else get(flag)
    if target isnt? none return read(target)
    return 42
}
main=():>int64=>work(true 42)
"""
CASES = [
    SOURCE,
    SOURCE.replace('work(true 42)', 'work(false 42)'),
    SOURCE.replace('else get(flag)', 'else none'),
    SOURCE.replace('let target=if flag value else get(flag)',
                   'let target:addr?=none target=if flag value else get(flag)'),
]
ERRORS = [
    SOURCE.replace('get=(flag:bool):>addr?=>if flag 42 as addr else none',
                   'get=(flag:bool):>int64?=>-1'),
    SOURCE.replace('if target isnt? none return read(target)', 'return read(target)'),
    SOURCE.replace('if target isnt? none return read(target)',
                   'target=-1 if target isnt? none return read(target)'),
]


@pytest.mark.parametrize('source', CASES)
def test_optional_conditional_payload_bounds(source, tmp_path):
    execute(tmp_path, 'optional-conditional-bounds', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_optional_payload_bounds_require_all_present_paths(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_optional_conditional_payload_bounds(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
