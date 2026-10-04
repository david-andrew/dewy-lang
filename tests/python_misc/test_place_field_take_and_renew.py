"""A field taken from a place parameter moves when every path stores it back.

The caller reads the whole parameter after the call, so on leaving the
function every field of a place parameter is live. A store to a fixed field
path renews it: before the store only the sibling fields stay live. A field
taken out and stored back before every exit is therefore a move. An exit,
or a read of the whole parameter, between the take and the store keeps the
copy, and so does a take that is never stored back."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type = [values:array<int64>]
Holder:type = [current:State count:int64=0 pages:dict<int64 State>=[] names:dict<string int64>=[] items:array<int64>=[] shelf:dict<int64 array<int64>>=[]]
values=(n:int64):>array<int64>=>{
    let result:array<int64>=[]
    let i:int64=0
    loop i <? n {result.push(i) i+=1}
    return result
}
touch=(@h:Holder):>void=>{h.count+=h.current.values.length}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''# Saved around work that sees an empty field, then restored.
around=(@h:Holder n:int64):>void=>{
    let saved=h.current
    h.current=State[values(n)]
    touch(@h)
    saved.values.push(9)
    h.current=saved
}
# Filed away, and the field replaced.
file=(@h:Holder key:int64 n:int64):>void=>{
    h.pages[key]=h.current
    h.current=State[values(n)]
}
# Replaced on one arm only after the take on that arm.
either=(@h:Holder flag:bool):>void=>{
    if flag {
        let saved=h.current
        saved.values.push(7)
        h.current=saved
    }
}
# A dictionary saved around work and restored (the SSA builder's names).
rename=(@h:Holder):>void=>{
    let saved=h.names
    h.names=[]
    h.names['inner']=1
    touch(@h)
    saved['outer']=2
    h.names=saved
}
# The current page filed under its number and a new one started.
page=(@h:Holder to:int64):>void=>{
    if h.count not=? to {
        h.shelf[h.count]=h.items
        h.items=values(to)
        h.count=to
    }
}
main=():>int64=>{
    let h=Holder[State[values(3)]]
    around(@h 5)
    file(@h 1 2)
    either(@h true)
    either(@h false)
    let filed=h.pages.get(1)
    let filed_length=if filed is? none 0 else filed.values.length
    let ok=h.count =? 5 and filed_length =? 4 and h.current.values.length =? 3
    rename(@h)
    h.items=values(4)
    page(@h 1)
    let started=h.items.length =? 1 and h.count =? 1
    page(@h 8)
    let shelved=h.shelf.get(8)
    let shelved_length=if shelved is? none 0 else shelved.length
    ok=ok and started and h.count =? 8 and h.items.length =? 8 and shelved_length =? 4 and h.names.length =? 1 and h.names.get('outer' default=0) =? 2
    return if ok 42 else 1
}
'''
# Each of these observes the old field value, so it stays a copy.
EARLY_EXIT = PRELUDE + '''early=(@h:Holder n:int64):>int64=>{
    let saved=h.current
    saved.values.push(9)
    if n >? 2 return saved.values.length
    h.current=State[values(n)]
    return 0
}
main=():>int64=>{
    let h=Holder[State[values(3)]]
    let first=early(@h 5)
    return if first =? 4 and h.current.values.length =? 3 42 else 1
}
'''
WHOLE_READ = PRELUDE + '''watched=(@h:Holder):>void=>{
    let saved=h.current
    saved.values.push(9)
    touch(@h)
    h.current=saved
}
main=():>int64=>{
    let h=Holder[State[values(3)]]
    watched(@h)
    return if h.count =? 3 and h.current.values.length =? 4 42 else 1
}
'''
NEVER_STORED = PRELUDE + '''kept=(@h:Holder):>int64=>{
    let saved=h.current
    saved.values.push(9)
    return saved.values.length
}
main=():>int64=>{
    let h=Holder[State[values(3)]]
    return if kept(@h) =? 4 and h.current.values.length =? 3 42 else 1
}
'''
CASES = [MOVED, EARLY_EXIT, WHOLE_READ, NEVER_STORED]
ERRORS = ['$explicit_copies\n' + source for source in (EARLY_EXIT, WHOLE_READ, NEVER_STORED)]


@pytest.mark.parametrize('source', CASES)
def test_place_field_take_and_renew(tmp_path, source):
    execute(tmp_path, 'place-field-renew', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_observed_place_field_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_place_field_take_and_renew(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
