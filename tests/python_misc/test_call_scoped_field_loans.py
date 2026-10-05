"""A call may borrow a parameter or local that is written elsewhere.

A call-scoped loan (a direct argument, or a field of a record literal built
for the call) needs its storage for the call only. A parameter, or a local
that starts fresh and is only ever replaced by fresh values, keeps that
storage for a call that cannot write it, although it is written elsewhere in
the function: no argument expression writes it or passes it to a nested
call, and the call passes it only to read-only parameters. Passing an
overlapping place, or writing it while the arguments are evaluated, keeps
the copy.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''Links:type=[edges:array<int64>]
Session:type=[links:Links types:array<int64> count:int64=0]
System:type=[links:Links extra:array<int64>]
const promotions:array<int64>=[1 2]
promote=(x:int64 system:System @types:array<int64>):>int64=>{
    types.push(x)
    return system.links.edges.length+system.extra.length
}
'''
BORROWED = '$explicit_copies\n' + PRELUDE + '''check=(x:int64 @session:Session):>int64=>{
    session.links.edges.push(x)
    let p=promote(x System[session.links promotions] @session.types)
    session.count+=p
    return p
}
main=():>int64=>{
    let s=Session[Links[[1]] []]
    let r=check(3 @s)
    return r+check(4 @s)+33
}
'''
# The callee receives the whole session as a place and may write the field.
WHOLE_PLACE = PRELUDE + '''grow=(system:System @session:Session):>int64=>{
    session.links.edges.push(9)
    return system.links.edges.length
}
check=(x:int64 @session:Session):>int64=>{
    session.links.edges.push(x)
    return grow(System[session.links promotions] @session)
}
main=():>int64=>{
    let s=Session[Links[[1]] []]
    return check(3 @s)+40
}
'''
# A later argument writes the field before the call runs.
ARGUMENT_WRITE = PRELUDE + '''bump=(@links:Links):>int64=>{
    links.edges.push(5)
    return links.edges.length
}
measure=(system:System n:int64):>int64=>system.links.edges.length*10+n
check=(@session:Session):>int64=>{
    session.count+=1
    return measure(System[session.links promotions] bump(@session.links))
}
main=():>int64=>{
    let s=Session[Links[[1]] []]
    return check(@s)+30
}
'''
# A local replaced by each call's result is lent to that call.
REPLACED = '$explicit_copies\n' + PRELUDE + '''widen=(items:array<int64> n:int64):>array<int64>=>{
    let output:array<int64>=[]
    loop item in items {output.push(item) output.push(item+n)}
    return output
}
count=(edges:array<int64>):>int64=>edges.length
check=(@session:Session):>int64=>{
    session.links.edges.push(2)
    return count(session.links.edges)
}
main=():>int64=>{
    let items:array<int64>=[1]
    let i:int64=0
    loop i <? 3 {
        items=widen(items i)
        i+=1
    }
    let s=Session[Links[[1]] []]
    return items.length+check(@s)+32
}
'''
# The second argument writes the local the first one lends.
LOCAL_WRITE = PRELUDE + '''bump=(@items:array<int64>):>int64=>{
    items.push(5)
    return items.length
}
measure=(items:array<int64> n:int64):>int64=>items.length*10+n
fill=(n:int64):>array<int64>=>{
    let result:array<int64>=[]
    let i:int64=0
    loop i <? n {result.push(i) i+=1}
    return result
}
main=():>int64=>{
    let items=fill(1)
    items=fill(2)
    return measure(items bump(@items))+19
}
'''
CASES = [BORROWED, WHOLE_PLACE, ARGUMENT_WRITE, REPLACED, LOCAL_WRITE]
ERRORS = ['$explicit_copies\n' + source for source in (WHOLE_PLACE, ARGUMENT_WRITE, LOCAL_WRITE)]


@pytest.mark.parametrize('source', CASES)
def test_call_scoped_field_loans(tmp_path, source):
    execute(tmp_path, 'field-loans', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_written_field_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_call_scoped_field_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
