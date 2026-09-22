"""A stable read-only union can lend its tag and payload across a call."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute

CASES=[
    '''read=(x:array<int64>|none):>int64 & no_effects=>if x isnt? none x.length else 0
forward=(x:array<int64>|none):>int64 & no_effects=>read(x)
work=(x:array<int64>|none):>int64=>{let before=_arena_allocated_bytes let value=forward(x)
return if _arena_allocated_bytes=?before and value=?2 42 else 1}
main=():>int64=>work([40 2])''',
    '''Box:type=[value:int64]
read=(x:Box|none):>int64 & no_effects=>if x isnt? none x.value else 42
forward=(x:Box|none):>int64 & no_effects=>read(x)
work=(x:Box|none):>int64=>{let before=_arena_allocated_bytes let value=forward(x)
return if _arena_allocated_bytes=?before value else 1}
main=():>int64=>if work(Box[42])=?42 work(none) else 1''',
    '''Box:type=[value:int64]
Choice:type=Box|array<int64>|none
read=(x:Choice):>int64 & no_effects=>{if x is? Box return x.value if x is? array<int64> return x.length return 42}
forward=(x:Choice):>int64 & no_effects=>read(x)
main=():>int64=>if forward([1 2])=?2 and forward(none)=?42 forward(Box[42]) else 1''',
    '''read=(x:string|none):>int64 & no_effects=>if x isnt? none x.length else 0
forward=(x:string|none):>int64 & no_effects=>read(x)
work=(x:string|none):>int64=>{let before=_arena_allocated_bytes let value=forward(x)
return if _arena_allocated_bytes=?before and value=?2 42 else 1}
main=():>int64=>work("hi")''',
    '''Box:type=[value:int64]
Holder:type=[choice:Box|none]
read=(x:Box|none):>int64 & no_effects=>if x isnt? none x.value else 0
forward=(x:Holder):>int64 & no_effects=>read(x.choice)
main=():>int64=>forward(Holder[Box[42]])''',
]
CASES += [
    '''Box:type=[value:int64]
change=(x:Box|none):>void=>{if x isnt? none {x.value=1}}
work=(x:Box|none):>int64=>{change(x) return if x isnt? none x.value else 0}
main=():>int64=>work(Box[42])''',
    '''read=(x:array<int64>|none):>int64 & no_effects=>if x isnt? none x.length else 0
forward=(x:array<int64>|none count:int64):>int64 & no_effects=>{
if count>?0 return forward(x count-1) return read(x)}
work=(x:array<int64>|none):>int64=>{let before=_arena_allocated_bytes let value=forward(x 100)
return if _arena_allocated_bytes=?before and value=?2 42 else 1}
main=():>int64=>work([40 2])''',
    '''Box:type=[value:int64]
read=(x:Box|none):>int64 & no_effects=>if x isnt? none x.value else 0
forward=(x:Box|none flag:bool):>int64 & no_effects=>if flag read(x) else read(x)
main=():>int64=>if forward(Box[42] true)=?42 forward(Box[42] false) else 1''',
]

CASES += [
    '''Box:type=[value:int64]
read=(x:Box|none=none):>int64 & no_effects=>if x isnt? none x.value else 42
forward=(x:Box|none):>int64 & no_effects=>read(x)
work=(x:Box|none):>int64=>{let before=_arena_allocated_bytes let value=forward(x)
return if _arena_allocated_bytes=?before and read()=?42 value else 1}
main=():>int64=>work(Box[42])''',
    '''Box:type=[value:int64]
read=(x:Box|none=Box[42]):>int64=>if x isnt? none x.value else 0
main=():>int64=>{let before=_arena_live_bytes let i:int64=0
loop i<?100 {if read() not=?42 return 1 i+=1}
return if _arena_live_bytes=?before 42 else 2}''',
]

CASES += [
    '''Box:type=[value:int64]
copy=(x:Box|none=none):>Box|none=>x
work=(x:Box|none):>int64=>{let saved=copy(x)
if saved isnt? none {saved.value=1}
return if x isnt? none x.value else 0}
main=():>int64=>work(Box[42])''',
]

CASES += [
    '''Box:type=[value:int64]
Choice:type=Box|array<int64>|none
read=(x:Choice=none):>int64 & no_effects=>{if x is? Box return x.value if x is? array<int64> return x.length return 42}
forward=(x:Choice):>int64 & no_effects=>read(x)
work=(x:Choice):>int64=>{let before=_arena_allocated_bytes let value=forward(x)
return if _arena_allocated_bytes=?before and read()=?42 value else 1}
main=():>int64=>work(Box[42])''',
]

CASES += [
    '''Box:type=[value:int64]
Choice:type=Box|string|none
Holder:type=[first:Choice second:Choice]
fill=(@x:Choice):>void=>{x=Box[42]}
main=():>int64=>{let left:Choice=none let right:Choice=none
fill(@left) if right isnt? none return 1
let holder=Holder[none none] fill(@holder.first)
if holder.second isnt? none return 2
let items:array<Choice>=[none none] fill(@items[0])
if items[1] isnt? none return 3
if left is? Box and holder.first is? Box and items[0] is? Box return left.value
return 4}''',
    '''Box:type=[value:int64]
Choice:type=Box|array<int64>|none
read=(x:Choice=none):>int64 & no_effects=>if x is? none 42 else 0
main=():>int64=>{let before=_arena_allocated_bytes let count:int64=0
loop count<?100 {if read() not=?42 return 1 count+=1}
return if _arena_allocated_bytes=?before 42 else 2}''',
]

CASES += [
    '''Box:type=[value:int64]
Choice:type=Box|string|none
fill=(@x:Choice):>void=>{x=Box[42]}
main=():>int64=>{let values:totaldict<("a"|"b") Choice>=["a"->none "b"->none]
values["a"]=Box[42]
return if values["a"] is? Box and values["b"] is? none 42 else 1}''',
    '''Box:type=[value:int64]
fill=(@x:Box|none):>void=>{x=Box[42]}
main=():>int64=>{let values:array<Box|none>=[none none]
fill(@values[0]) return if values[0] is? Box and values[1] is? none 42 else 1}''',
]

ERRORS=[
    "Box:type=[value:int64]\nforward=(x:Box|none):>Box|none & no allocates=>x",

    '''Box:type=[value:int64]
change=(x:Box|none):>int64=>{if x isnt? none {x.value=1 return x.value} return 0}
forward=(x:Box|none):>int64 & no allocates=>change(x)''',
    '''Box:type=[value:int64]
read=(x:Box|none):>int64=>if x isnt? none x.value else 0
forward=(x:Box|none f:(Box|none):>int64):>int64 & no_effects=>f(x)''',
    '''Box:type=[value:int64]
copy=(x:Box|none):>Box|none & no allocates=>x.copy()''',
]

@pytest.mark.parametrize('source',CASES)
def test_union_forwarding_lends_stable_storage(source,tmp_path):
    execute(tmp_path,'union-borrow',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_union_forwarding_needs_complete_storage_proof(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))

def test_native_union_forwarding(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
