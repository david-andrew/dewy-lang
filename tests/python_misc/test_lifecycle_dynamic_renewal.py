"""Replacing a partially consumed array retires its remainder and restores ownership."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_lifecycle_dynamic_siblings import HEADER, BODY

RENEW = (HEADER + BODY).replace('return owner.sibling.id',
    'owner.items=[Token[4]]\n    return owner.sibling.id').replace(
    'trace not=?1532', 'trace not=?15234').replace('trace=?5321', 'trace=?52134')
CASES = [RENEW,
    RENEW.replace('let owner=Bundle[[Token[1] Token[2]] Token[3]]',
                  'let owners=[Bundle[[Token[1] Token[2]] Token[3]]]').replace('owner.', 'owners[0].'),
    RENEW.replace('owner.items=[Token[4]]', 'owner.items=[{index=1 Token[4]}]'),
    RENEW.replace('Bundle:type=[items:array<Token> sibling:Token]',
        'Bundle:type=[items:array<Token> sibling:Token]\nOuter:type=[bundle:Bundle]')
        .replace('let owner=Bundle[[Token[1] Token[2]] Token[3]]',
                 'let outer=Outer[Bundle[[Token[1] Token[2]] Token[3]]]').replace('owner.', 'outer.bundle.'),
]
LOOP = HEADER + '''probe=(index:int64):>int64=>{
    let owner=Bundle[[Token[1] Token[2]] Token[3]]
    loop repeat in 0..2 {
        if index>=?0 and index<?owner.items.length {consume(owner.items[index])}
        owner.items=[Token[1] Token[2]]
    }
    return owner.sibling.id
}
main=():>int64=>{
    let before=_arena_live_bytes
    loop repeat in 0..49 {trace=0 if probe(0) not=?3 or trace not=?121212321 return 1}
    return if _arena_live_bytes=?before 42 else 2
}'''
CASES.append(LOOP)
CASES.append(HEADER + """Pair:type=[left:array<Token> right:array<Token>]
Outer:type=[pair:Pair sibling:Token]
probe=(index:int64):>void=>{
    let owner=Outer[Pair[[Token[1] Token[2]] [Token[3] Token[4]]] Token[5]]
    if index>=?0 and index<?owner.pair.left.length {consume(owner.pair.left[index])}
    if index>=?0 and index<?owner.pair.right.length {consume(owner.pair.right[index])}
    owner.pair=Pair[[Token[6]] [Token[7]]]
}
main=():>int64=>{probe(0) return if trace=?1342576 42 else 1}
""")
ERRORS = [RENEW.replace('owner.items=[Token[4]]', text) for text in [
    'owner.items[0]=Token[4]',
    'owner.items=[Token[owner.items[0].id]]',
    'if index=?1 {owner.items=[Token[4]]}\n    let again=owner.items',
]]


@pytest.mark.parametrize('source', CASES)
def test_dynamic_array_renewal(tmp_path, source):
    execute(tmp_path, 'dynamic-renewal', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_dynamic_array_renewal_requires_complete_replacement(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dynamic_array_renewal(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
