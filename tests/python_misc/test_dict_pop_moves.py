"""A dictionary `pop` moves an array value out of the dictionary.

The entry is removed, so the dictionary no longer needs its value: `pop`
takes the array's handle, with the reference it holds, and leaves nothing in
the tombstoned slot. The result is the caller's own value and binding or storing
it is not a copy. A default that is not itself fresh keeps the copy, and
a record value, which may be shared, is read as before."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type = [values:array<int64>]
Holder:type = [items:array<int64>=[] shelf:dict<int64 array<int64>>=[]]
values=(n:int64):>array<int64>=>{
    let result:array<int64>=[]
    let i:int64=0
    loop i <? n {result.push(i) i+=1}
    return result
}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''arrays=():>int64=>{
    let shelf:dict<int64 array<int64>>=[]
    loop i in 0..6 {shelf[i]=values(i)}
    let got:array<int64>=[]
    if 3 in? shelf {got=shelf.pop(3)}
    got.push(9)
    let other=shelf.pop(4 default=[])
    let missing=shelf.pop(40 default=[])
    # Iterating compacts the remaining entries past the tombstones.
    let total:int64=0
    loop [key value] in shelf {total+=key*10+value.length}
    return got.length*1000+other.length*100+missing.length*10+total+shelf.length
}
fields=(@h:Holder):>void=>{
    h.shelf[1]=h.items
    h.items=h.shelf.pop(2 default=[])
}
main=():>int64=>{
    let h=Holder[values(3)]
    h.shelf[2]=values(5)
    fields(@h)
    let ok=arrays() =? 4559 and h.items.length =? 5
    return if ok 42 else 1
}
'''
# A record value may be shared, so `pop` reads it as before; the dictionary
# stays consistent around it.
SHARED = PRELUDE + '''records=():>int64=>{
    let states:dict<string State>=[]
    states['a']=State[values(2)]
    states['b']=State[values(5)]
    let taken=State[[]]
    if 'a' in? states {taken=states.pop('a')}
    taken.values.push(7)
    states['a']=State[values(1)]
    let again=states.get('a')
    let again_length=if again is? none 0 else again.values.length
    return taken.values.length*100+again_length*10+states.length
}
# A page of a dictionary of dictionaries taken out and filed back.
pages=():>int64=>{
    let filed:dict<int64 dict<int64 int64>>=[]
    let first_page:dict<int64 int64>=[]
    first_page[1]=10
    filed[0]=first_page
    let second_page=filed.pop(1 default=[])
    second_page[2]=20
    filed[1]=second_page
    let back=filed.pop(0 default=[])
    let first=back.get(1 default=0)
    let second=filed.get(1)
    let second_value=if second is? none 0 else second.get(2 default=0)
    return first+second_value+filed.length
}
main=():>int64=>if records() =? 312 and pages() =? 31 42 else 1
'''
# The default is still read afterwards, so the result may be the default's
# storage: binding it copies.
KEPT_DEFAULT = PRELUDE + '''main=():>int64=>{
    let shelf:dict<int64 array<int64>>=[]
    let fallback=values(2)
    let got=shelf.pop(1 default=fallback)
    got.push(9)
    return if got.length =? 3 and fallback.length =? 2 42 else 1
}
'''
CASES = [MOVED, SHARED, KEPT_DEFAULT]
ERRORS = ['$explicit_copies\n' + KEPT_DEFAULT]


@pytest.mark.parametrize('source', CASES)
def test_dict_pop_moves(tmp_path, source):
    execute(tmp_path, 'dict-pop', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_kept_default_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_dict_pop_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
