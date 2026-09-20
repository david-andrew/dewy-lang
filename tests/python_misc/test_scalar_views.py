"""Scalar view demands retain width/sign and the same stable-owner proof."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


@pytest.mark.parametrize('body', [
    'let value:uint64=18446744073709551615 const view=@value return if view >? 9223372036854775807 42 else 1',
    'let value:int8=-42 const view=@value return if view <? 0 42 else 1',
    'let value:bool=true const view=@value return if view 42 else 1',
    'let value:int64< v => v >? 0>=42 const view=@value return view',
    'let values:array<uint8 length=1>=[42] const view=@values[0] return view as int64',
    'let value=[answer=42] const view=@value.answer return view',
    "let values:dict<string int64>=['answer' -> 42] const view=@values return view['answer']",
    'let values:set<int64>=set[42] const view=@values return if 42 in? view 42 else 1',
    "let words:array<string>=['forty' 'two'] const view=@words return if view.join('-')=?'forty-two' 42 else 1",
])
def test_scalar_and_container_views(tmp_path, body):
    execute(tmp_path, 'scalar-view', codegen(SrcFile(None, 'main=():>int64=>{'+body+'}'), debug_locations=False))


def test_scalar_view_without_prelude(tmp_path):
    execute(tmp_path, 'scalar-no-prelude', codegen(SrcFile(None, '$no_prelude=true main=():>int64=>{let value:int64=42 const view=@value return view}'), debug_locations=False))


@pytest.mark.parametrize('write', ['value=99', 'touch(@value)'])
def test_scalar_view_requires_owner_stability(write):
    source = SrcFile(None, 'touch=(@value:int64):>void=>{value=99} main=():>int64=>{'
                     'let value:int64=42 const view=@value '+write+' return view}')
    with pytest.raises(ReportException, match='cannot prove required local view'):
        codegen(source)
