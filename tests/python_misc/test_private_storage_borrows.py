"""Fresh unexposed owners stay stable across effects on unrelated storage."""
from pathlib import Path

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PRIVATE = '''$explicit_copies
let counter:int64=0
tick=():>void=>{counter+=1}
work=(flag:bool):>int64=>{
 let owner:array<int64>=[42]
 const selected=if flag owner else [42]
 tick()
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>{
 if work(true) not=?42 or work(false) not=?42 return 1
 let before:int64=_arena_allocated_bytes
 loop i in [0..1000) {if work(true) not=?42 return 2}
 return if _arena_allocated_bytes=?before and counter=?1002 42 else 3
}'''
CASES = [PRIVATE, '''$explicit_copies
let counter:int64=0
tick=():>void=>{counter+=1}
Box:type=[items:array<int64>]
make=():>Box|none=>Box[[42]]
work=():>int64=>{
 let value=make()
 const items:array<int64>=if value is? Box value.items else []
 tick()
 return if items.length>?0 items[0] else 1
}
main=():>int64=>work()''', '''$explicit_copies
let counter:int64=0
tick=():>void=>{counter+=1}
Box:type=[items:array<int64>]
work=():>int64=>{
 let owner=Box[[42]]
 const values=owner.items
 tick()
 return if values.length>?0 values[0] else 1
}
main=():>int64=>work()''', '''$explicit_copies
let counter:int64=0
tick=():>void=>{counter+=1}
read=(items:array<int64>):>int64=>if items.length>?0 items[0] else 1
work=():>int64=>{
 let owner:array<int64>=[42]
 tick()
 return read(owner)
}
main=():>int64=>work()''']

# Incoming storage still needs the graph alias guard. Direct writes, captures
# and address exposure cannot enter the private-owner proof either.
ERRORS = [PRIVATE.replace('work=', 'make=():>array<int64>=>[42]\nwork=',1).replace('let owner:array<int64>=[42]', 'let owner=make()').replace(' tick()',' owner.clear()\n tick()'),
'''$explicit_copies
let global:array<int64>=[42]
change=():>void=>{global.clear()}
work=(incoming:array<int64> flag:bool):>int64=>{
 const selected=if flag incoming else [42]
 change()
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>work(global true)''',

'''$explicit_copies
make=():>array<int64>=>[42]
work=(flag:bool):>int64=>{
 let owner=make()
 const selected:array<int64>=if flag owner else []
 let pointer=owner transmute int64
 return if selected.length>?0 selected[0] else pointer
}
main=():>int64=>work(true)''']

# A resolved read-only capture may already have a safe independent ABI.
CASES.append('''make=():>array<int64>=>[42]
work=(flag:bool):>int64=>{
 let owner=make()
 read=():>int64=>if owner.length>?0 owner[0] else 0
 const selected:array<int64>=if flag owner else []
 let observed=read()
 if observed not=?42 return 2
 return if selected.length>?0 selected[0] else 1
}
main=():>int64=>work(true)''')

ERRORS.append('$explicit_copies\n'+CASES[-1])

@pytest.mark.parametrize('source', CASES)
def test_private_storage_borrow(tmp_path, source):
    execute(tmp_path, 'private-storage', codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_private_storage_requires_independence(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None,source),debug_locations=False)

def test_native_private_storage_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
