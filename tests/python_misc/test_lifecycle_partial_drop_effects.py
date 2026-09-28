"""A drop hook can observe surviving fields of a partially transferred owner."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = '''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Wrapper=type of [first:Token second:Token marker:int64
    $__drop__ release=():>void=>{trace=trace*10+marker}
]
consume=(value:Token):>int64=>value.id
'''
SOURCE = HEADER + '''work=(flag:bool):>int64=>{
    let owner=Wrapper[Token[1] Token[2] 3]
    if flag {consume(owner.first);}
    return owner.second.id
}
main=():>int64=>{
    if work(true) not=?2 or trace not=?132 return 1
    trace=0
    return if work(false)=?2 and trace=?321 42 else 2
}
'''
RETURN = HEADER + '''take=():>Token=>{
    let owner=Wrapper[Token[1] Token[2] 3]
    return owner.first
}
work=():>int64=>{
    let value=take()
    return if value.id=?1 and trace=?32 42 else 1
}
main=():>int64=>{let result=work() return if trace=?321 result else 2}
'''
CASES = [SOURCE, RETURN]
ERRORS = [SOURCE.replace('trace*10+marker', expression) for expression in ['trace*10+first.id', 'trace*10+first.id+second.id']]

# A helper's transitive summary participates in exactly the same route check.
helper='read_id=(@value:Token):>int64=>value.id\n'
indirect=SOURCE.replace('Wrapper=type of', helper+'Wrapper=type of').replace('trace*10+marker', 'trace*10+read_id(@second)').replace('trace not=?132','trace not=?122').replace('trace=?321','trace=?221')
CASES.append(indirect)
ERRORS.append(indirect.replace('read_id(@second)', 'read_id(@first)'))
CASES.append(SOURCE.replace('trace=trace*10+marker}', 'trace=trace*10+marker second.id=4}').replace('trace not=?132','trace not=?134').replace('trace=?321','trace=?341'))
ERRORS.append(SOURCE.replace('trace=trace*10+marker}', 'trace=trace*10+marker first.id=4}'))

nested=SOURCE.replace('consume=', 'Outer=type of [inner:Wrapper marker:int64 $__drop__ release=():>void=>{trace=trace*10+marker}]\nconsume=').replace('let owner=Wrapper[Token[1] Token[2] 3]', 'let owner=Outer[Wrapper[Token[1] Token[2] 3] 9]').replace('owner.first','owner.inner.first').replace('owner.second','owner.inner.second').replace('trace not=?132','trace not=?1932').replace('trace=?321','trace=?9321')
CASES.append(nested)
ERRORS.append(nested.replace('marker:int64 $__drop__ release=():>void=>{trace=trace*10+marker}', 'marker:int64 $__drop__ release=():>void=>{trace=trace*10+inner.first.id}'))
dynamic=SOURCE.replace('first:Token', 'first:array<Token>').replace('Wrapper[Token[1] Token[2] 3]', 'Wrapper[[Token[1] Token[4]] Token[2] 3]').replace('work=(flag:bool)', 'work=(flag:bool slot:int64)').replace('if flag {consume(owner.first);}', 'if slot<?0 or slot>=?owner.first.length return 0\n    if flag {consume(owner.first[slot]);}').replace('work(true)', 'work(true 0)').replace('work(false)', 'work(false 0)').replace('trace not=?132', 'trace not=?1324').replace('trace=?321','trace=?3241')
CASES.append(dynamic)

@pytest.mark.parametrize('source', CASES)
def test_partial_drop_uses_surviving_fields(tmp_path, source):
    execute(tmp_path, 'partial-drop-effects', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_partial_drop_cannot_read_consumed_fields(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_partial_drop_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
