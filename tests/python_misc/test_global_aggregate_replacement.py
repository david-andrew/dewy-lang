"""A global owns replacement storage and releases its previous value."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

RECORD = '$explicit_copies\nBox:type=[items:array<int64> spare:array<int64>]\nmake=(n:int64):>Box=>Box[[n 22] [3 4]]\nlet kept=Box[[] []]\ntake=(n:int64):>array<int64>=>{\n    let owner=make(n)\n    kept=owner.copy()\n    let result=owner.items\n    if owner.spare.length not=?2 return []\n    return result\n}\nwork=():>int64=>{\n    let items=take(20)\n    if items.length not=?2 return 1\n    items[0]=items[0]+1\n    if kept.items.length not=?2 or kept.items[0] not=?20 return 4\n    return items[0]+items[1]-1\n}\nmain=():>int64=>{\n    if work() not=?42 return 1\n    let before:int64=_arena_live_bytes\n    loop i in [0..1000) {if work() not=?42 return 2}\n    return if _arena_live_bytes=?before 42 else 3\n}\n'
ARRAY = '''$explicit_copies
let saved:array<int64>=[]
update=(n:int64):>void=>{saved=[n 22]}
work=():>int64=>{
    update(20)
    let held=saved.copy()
    saved=saved.copy()
    if saved.length not=?2 return 1
    saved[0]=21
    return if held.length=?2 and held[0]=?20 saved[0]+saved[1]-1 else 2
}
main=():>int64=>{
    if work() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..1000) {if work() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [RECORD, ARRAY,
    ARRAY.replace('let saved:array<int64>=[]', 'let saved:array<int64 length=2>=[0 0]'),
    ARRAY.replace('update(20)', 'update(20) update(20)'),
    ARRAY.replace('work=():>', 'saved=[1 2]\nwork=():>'),
]
NESTED = ARRAY.replace('let saved:array<int64>=[]', 'let saved:array<array<int64>>=[]')
NESTED = NESTED.replace('saved=[n 22]', 'saved=[[n 22]]')
NESTED = NESTED.replace('saved.length not=?2', 'saved.length not=?1 or saved[0].length not=?2')
NESTED = NESTED.replace('saved[0]=21', 'saved[0][0]=21').replace('saved[0]+saved[1]-1', 'saved[0][0]+saved[0][1]-1')
NESTED = NESTED.replace('held.length=?2 and held[0]=?20', 'held.length=?1 and held[0].length=?2 and held[0][0]=?20')
CASES.append(NESTED)

@pytest.mark.parametrize('source', CASES)
def test_global_aggregate_replacement(tmp_path, source):
    execute(tmp_path, 'global-aggregate', codegen(SrcFile(None, source), debug_locations=False))

def test_native_global_aggregate_replacement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])

# Module statements have persistent owners but no function cleanup frame.
CASES.append('''$explicit_copies
let saved:array<int64>=[]
saved=[1 2]
let baseline:int64=_arena_live_bytes
saved=[20 22]
let final:int64=_arena_live_bytes
main=():>int64=>if final=?baseline and saved.length=?2 saved[0]+saved[1] else 1
''')
CASES.append('''$explicit_copies
Box:type=[text:string items:array<string>]
let saved=Box['' []]
update=(n:int64):>void=>{let text="{n}" saved=Box[text [text]]}
work=():>int64=>{
    update(42)
    return if saved.text=?'42' and saved.items.length=?1 and saved.items[0]=?'42' 42 else 1
}
main=():>int64=>{
    if work() not=?42 return 1
    let baseline:int64=_arena_live_bytes
    loop i in [0..1000) {if work() not=?42 return 2}
    return if _arena_live_bytes=?baseline 42 else 3
}
''')
