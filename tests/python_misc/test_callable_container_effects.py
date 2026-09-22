"""Container inference joins callable effects without changing call signatures."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


PURE = '''left=(value:int64):>int64=>value+1
right=(value:int64):>int64=>value-1
apply=(f:(value:int64):>int64 & no_effects):>int64 & no_effects=>f(41)
main=():>int64=>{let handlers=[@left @right] return apply(handlers[0])}'''

EFFECTFUL = '''let state:int64=0
left=(value:int64):>int64=>value+1
right=(value:int64):>int64=>{state+=1 return value+1}
apply=(f:(value:int64):>int64 & no_effects):>int64 & no_effects=>f(41)
main=():>int64=>{let handlers=[@left @right] return apply(handlers[0])}'''

UNKNOWN = '''collect=(left:(value:int64):>int64 right:(value:int64):>int64):>int64=>{
    let handlers=[@left @right]
    return apply(handlers[0])
}
apply=(f:(value:int64):>int64 & no_effects):>int64 & no_effects=>f(41)
main=():>int64=>42'''

REJECTED = [EFFECTFUL, EFFECTFUL.replace('[@left @right]', '[@right @left]'), UNKNOWN]


def test_pure_callable_array_retains_inferred_purity(tmp_path):
    execute(tmp_path, 'pure-callable-array', codegen(SrcFile(None, PURE)))


@pytest.mark.parametrize('source', REJECTED)
def test_callable_array_cannot_discard_effectful_or_unknown_alternatives(source):
    with pytest.raises(ReportException, match='effect contract|type mismatch'):
        codegen(SrcFile(None, source))


def test_native_callable_container_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[PURE], errors=REJECTED)
