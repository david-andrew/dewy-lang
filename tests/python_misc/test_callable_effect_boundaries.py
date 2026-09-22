"""Deferred effect checks must preserve a literal's calling convention."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


CASES = [
    '''let answer:<():>int64 & no_effects>=():>int64=>42
main=():>int64=>answer()''',
    '''main=():>int64=>{
    let box=[apply:<(value:int64):>int64 & no_effects>=(value:int64):>int64=>value+1]
    return box.apply(41)
}''',
    '''main=():>int64=>{
    let box=[apply:<(value:int64):>int64 & no_effects>=(value:int64):>int64=>value]
    box.apply=(value:int64):>int64=>value+1
    return box.apply(41)
}''',
]
REJECTED = '''let state:int64=0
main=():>int64=>{
    let box=[apply:<(value:int64):>int64 & no_effects>=(value:int64):>int64=>{state+=1 return value+1}]
    return box.apply(41)
}'''


@pytest.mark.parametrize('source', CASES)
def test_callable_boundary_preserves_literal_metadata(source, tmp_path):
    execute(tmp_path, 'callable-boundary', codegen(SrcFile(None, source)))


def test_method_boundary_still_checks_its_effect_obligation():
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, REJECTED))


def test_native_callable_effect_boundaries(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=CASES, errors=[REJECTED])
