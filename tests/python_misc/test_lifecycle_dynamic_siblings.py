"""An unknown element overlaps its containing array, not unrelated record fields."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = '''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Bundle:type=[items:array<Token> sibling:Token]
consume=(value:Token):>void=>{}
'''
BODY = '''probe=(flag:bool index:int64):>int64=>{
    let owner=Bundle[[Token[1] Token[2]] Token[3]]
    if flag and index>=?0 and index<?owner.items.length {consume(owner.items[index])}
    trace=trace*10+5
    return owner.sibling.id
}
main=():>int64=>{
    if probe(true 0) not=?3 or trace not=?1532 return 1
    trace=0
    return if probe(false 0)=?3 and trace=?5321 42 else 2
}'''
CASES = [HEADER + BODY,
    HEADER + BODY.replace('let owner=Bundle[[Token[1] Token[2]] Token[3]]', 'let owners=[Bundle[[Token[1] Token[2]] Token[3]]]').replace('owner.', 'owners[0].'),
]
CASES.append((HEADER + BODY).replace('return owner.sibling.id',
    'owner.sibling=Token[4]\n    return owner.sibling.id')
    .replace('not=?3 or trace not=?1532', 'not=?4 or trace not=?15342')
    .replace('=?3 and trace=?5321', '=?4 and trace=?53421'))
CASES.append((Path(__file__).parents[1] / 'fixtures/lifecycle_dynamic_siblings.dewy').read_text())
ERRORS = [HEADER + BODY.replace('return owner.sibling.id', statement + '\nreturn owner.sibling.id')
          for statement in [
              'if owner.items.length>?0 {let again=owner.items[0]}',
              'owner.items=[Token[4]]',
              'owner.items.push(Token[4])',
          ]]
ERRORS.append(HEADER + '''Both:type=[left:array<Token> right:array<Token>]
probe=(index:int64):>void=>{
let owner=Both[[Token[1] Token[2]] [Token[3] Token[4]]]
if index>=?0 and index<?owner.left.length and index<?owner.right.length {
    consume(owner.left[index])
    consume(owner.right[index])
}
}''')


@pytest.mark.parametrize('source', CASES)
def test_dynamic_component_keeps_sibling(tmp_path, source):
    execute(tmp_path, 'dynamic-sibling', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_dynamic_component_still_requires_container_last_use(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dynamic_component_keeps_sibling(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
