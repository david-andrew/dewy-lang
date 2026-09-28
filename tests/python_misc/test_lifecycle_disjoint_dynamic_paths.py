"""Dynamic cleanup carries each disjoint route's own presence predicate."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

HEADER = '''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Both:type=[left:array<Token> right:array<Token> sibling:Token]
consume=(value:Token):>void=>{}
'''
BODY = '''probe=(first:bool second:bool i:int64 j:int64):>void=>{
    let owner=Both[[Token[1] Token[2]] [Token[3] Token[4]] Token[5]]
    if first and i>=?0 and i<?owner.left.length {consume(owner.left[i])}
    if second and j>=?0 and j<?owner.right.length {consume(owner.right[j])}
    trace=trace*10+6
}
main=():>int64=>{
    probe(true true 0 1)
    if trace not=?146532 return 1
    trace=0
    probe(true false 0 1)
    if trace not=?165432 return 2
    trace=0
    probe(false true 0 1)
    if trace not=?465321 return 3
    trace=0
    probe(false false 0 1)
    return if trace=?654321 42 else 4
}'''
CASES = [HEADER + BODY]
CASES.append((HEADER + BODY).replace('let owner=Both[[Token[1] Token[2]] [Token[3] Token[4]] Token[5]]',
    'let owners=[Both[[Token[1] Token[2]] [Token[3] Token[4]] Token[5]]]').replace('owner.', 'owners[0].'))
CASES.append((HEADER + BODY).replace('    trace=trace*10+6', '    consume(owner.sibling)\n    trace=trace*10+6')
    .replace('146532', '145632').replace('165432', '156432').replace('465321', '456321').replace('654321', '564321'))
NESTED = (HEADER + BODY).replace('array<Token>', 'array<array<Token>>')
NESTED = NESTED.replace('Both[[Token[1] Token[2]] [Token[3] Token[4]]', 'Both[[[Token[1] Token[2]]] [[Token[3] Token[4]]]')
NESTED = NESTED.replace('i>=?0 and i<?owner.left.length', 'i>=?0 and owner.left.length>?0 and i<?owner.left[0].length')
NESTED = NESTED.replace('j>=?0 and j<?owner.right.length', 'j>=?0 and owner.right.length>?0 and j<?owner.right[0].length')
NESTED = NESTED.replace('owner.left[i]', 'owner.left[0][i]').replace('owner.right[j]', 'owner.right[0][j]')
CASES.append(NESTED)
# The nested traversal must carry both static and runtime presence flags.
CASES.append(CASES[1].replace('    trace=trace*10+6',
    '    if first {consume(owners[0].sibling)}\n    trace=trace*10+6')
    .replace('146532', '145632').replace('165432', '156432'))
CASES.append((HEADER + BODY).replace('    trace=trace*10+6', '    i+=1 j+=1\n    trace=trace*10+6'))
CASES.append((Path(__file__).parents[1] / 'fixtures/lifecycle_disjoint_dynamic_paths.dewy').read_text())
ERRORS = [HEADER + BODY.replace('consume(owner.right[j])', 'consume(owner.left[j])')]


@pytest.mark.parametrize('source', CASES)
def test_disjoint_dynamic_cleanup(tmp_path, source):
    execute(tmp_path, 'disjoint-dynamic', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_overlapping_dynamic_paths_remain_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_disjoint_dynamic_cleanup(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
