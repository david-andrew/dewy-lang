"""Sibling-field obligations refer to the current construction's bindings."""
import pytest
import test_bootstrap_check as source_values

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import TypeCheckError, UserError

INFO = 'BaseInfo:type=const[alphabet:string<2 <=? length <=? uint8.max> radix:uint8<radix =? alphabet.length>=alphabet.length]\n'
CASES = [
    INFO + "let main=():>int64=>{let info=BaseInfo['01'] return info.radix+40}",
    INFO + "let main=():>int64=>{let info=BaseInfo[alphabet='01' radix=2] return info.radix+40}",
    INFO + "let alphabet='outer'\nlet main=():>int64=>{let info:BaseInfo=[alphabet='01' radix=2] return info.radix+40}",
    "let main=():>int64=>{let info=[alphabet='01' radix:uint8<radix =? alphabet.length>=alphabet.length] return info.radix+40}",
    INFO + "let make=(alphabet:string<2 <=? length <=? uint8.max>):>BaseInfo=>BaseInfo[alphabet]\nlet main=():>int64=>make('01').radix+40",
    INFO + "let calls:int64=0\nlet next=():>string<2 <=? length <=? uint8.max>=>{calls+=1 return '01'}\nlet main=():>int64=>{let info=BaseInfo[next()] return (info.radix as int64)+calls+39}",
]
ERRORS = [
    INFO + "let main=():>int64=>{let info=BaseInfo[alphabet='01' radix=3] return info.radix}",
    INFO + "let alphabet='outer'\nlet main=():>int64=>{let info:BaseInfo=[alphabet='01' radix=5] return info.radix}",
    "let main=():>int64=>{let info=[alphabet='01' radix:uint8<radix =? alphabet.length>=3] return info.radix}",
    INFO + "let make=(radix:uint8):>BaseInfo=>BaseInfo['01' radix]\nlet main=():>int64=>make(2).radix",
]


@pytest.mark.parametrize('source', CASES)
def test_hosted_sibling_field_defaults(source):
    check.typecheck_and_resolve(SrcFile(None, source))


@pytest.mark.parametrize('source', ERRORS)
def test_hosted_invalid_sibling_fields(source):
    with pytest.raises((UserError, TypeCheckError), match='refinement'):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_native_sibling_field_sources(tmp_path, monkeypatch):
    # Invalid relational values remain obligations until validation. Runtime
    # positives and proof rejections are exercised by the graph driver.
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', [])
    source_values.test_native_source_values(tmp_path, function_types=True)
