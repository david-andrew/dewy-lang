"""Known type names retain receiver evaluation, including conditional dispatch."""
import pytest
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

STATIC = '''Item=type of [value:int64]
let calls:int64=0
make=():>Item=>{calls+=1 Item[42]}
main=():>int64=>{
    let name=make().typename
    return if name=?'Item' and calls=?1 42 else 1
}'''
DYNAMIC = '''Root=$abstract type of [value:int64]
let Child=type of Root
Grandchild=type of Child
let calls:int64=0
make=():>Root=>{calls+=1 Grandchild[42]}
main=():>int64=>{
    let name=if false make().typename else 'skip'
    if calls not=?0 or name not=?'skip' return 1
    name=make().typename
    return if name=?'Grandchild' and calls=?1 42 else 2
}'''
CASES=[STATIC, DYNAMIC,
       STATIC.replace('let name=make().typename', "let ignored=if false make().typename else 'skip'\n    if calls not=?0 return 2\n    let name=make().typename"),
       DYNAMIC.replace('let calls:int64=0', 'Box:type=[item:Root]\nlet calls:int64=0').replace('make=():>Root=>{calls+=1 Grandchild[42]}', 'make=():>Box=>{calls+=1 Box[Grandchild[42]]}').replace('make().typename', 'make().item.typename')]
CASES.append(DYNAMIC.replace('[value:int64]', "[value:int64 __as__=():>string=>'root']").replace('let Child=type of Root', "let Child=type of Root & [__as__=():>string=>'child']").replace('make().typename', '(make() as string)').replace("name=?'Grandchild'", "name=?'child'"))
CASES.append((Path(__file__).parents[1] / 'fixtures/type_name_borrowed_receiver.dewy').read_text())
ERRORS=[STATIC.replace('main=():>int64=>', 'main=():>int64 & no_effects=>')]

@pytest.mark.parametrize('source', CASES)
def test_type_name_receiver_effects(tmp_path, source):
    execute(tmp_path, 'type-name-effects', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_type_name_effect_contract(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_type_name_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
