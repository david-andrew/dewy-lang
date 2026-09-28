"""Unknown indices preserve disjoint fields, without proving indices distinct."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE='''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Pair:type=[left:Token right:Token]
consume=(value:Token):>void=>{}
work=(flag:bool i:int64 j:int64):>int64=>{
    let rows=[Pair[Token[1] Token[2]] Pair[Token[3] Token[4]]]
    if i<?0 or i>=?rows.length or j<?0 or j>=?rows.length return 0
    if flag {consume(rows[i].left)}
    let answer=rows[j].right.id
    consume(rows[j].right)
    return answer
}
main=():>int64=>{
    if work(true 0 1) not=?4 or trace not=?1432 return 1
    trace=0
    if work(true 0 0) not=?2 or trace not=?1243 return 2
    trace=0
    return if work(false 0 1)=?4 and trace=?4321 42 else 3
}
'''
CASES=[SOURCE, SOURCE.replace('    let answer=', '    i=1-i\n    let answer=')]
ERRORS=[SOURCE.replace('consume(rows[j].right)', 'consume(rows[j].left)'),
        SOURCE.replace('let answer=rows[j].right.id', 'let answer=rows[j].left.id'),
        SOURCE.replace('let answer=rows[j].right.id', 'rows[0].left=Token[9]\n    let answer=rows[j].right.id'),
        SOURCE.replace('let answer=rows[j].right.id', 'rows[j].left=Token[9]\n    let answer=rows[j].right.id'),
        SOURCE.replace('let answer=rows[j].right.id', 'rows[0]=Pair[Token[8] Token[9]]\n    let answer=rows[j].right.id')]

@pytest.mark.parametrize('source', CASES)
def test_dynamic_field_footprint(tmp_path, source):
    execute(tmp_path, 'dynamic-field-footprint', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_dynamic_field_overlap_keeps_owner(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dynamic_field_footprints(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
