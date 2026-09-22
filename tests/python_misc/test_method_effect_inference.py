"""A hidden receiver changes written slots, not a body's inferred row scope."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


PURE = '''Box=type of [base:int64 plus=(n:int64):>int64=>base+n]
main=():>int64=>Box[40].plus(2)'''

SETTER = '''Box=type of [base:int64 set=(@x:int64 @y:int64):>void=>{x=base}]
main=():>int64=>{let box=Box[42] let x:int64=0 let y:int64=0 box.set(@x @y) return x}'''

CASES = [PURE, SETTER, SETTER.replace(':>void=>', ':>void & mutates<x>=>')]
ERRORS = [
    'let state:int64=0\n' + PURE.replace(':>int64=>base+n', ':>int64 & no_effects=>{state+=1 return base+n}'),
    SETTER.replace(':>void=>', ':>void & mutates<y>=>'),
]


@pytest.mark.parametrize('source', CASES)
def test_method_inference_uses_the_complete_parameter_list(source, tmp_path):
    execute(tmp_path, 'method-row', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_method_inference_preserves_effect_obligations(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_method_effect_inference(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=CASES, errors=ERRORS)
