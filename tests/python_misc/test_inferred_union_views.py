"""Stable tagged projections share storage; mutation and escape retain ownership."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER='Box:type=[value:int64]\nChoice:type=Box|string|none\n'
CASES=[HEADER+body for body in [
'''read=(items:array<Choice>):>int64=>{if items.length=?0 return 1
let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=items[0] if item isnt? Box return 2 if item.value not=?42 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read([Box[42]])''',
'''read=(items:array<Box|none>):>int64=>{if items.length=?0 return 1
let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {let item=items[0] if item is? none return 2 if item.value not=?42 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read([Box[42]])''',
'''Holder:type=[choice:Choice]
read=(holder:Holder):>int64=>{let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=holder.choice if item isnt? Box return 2 if item.value not=?42 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read(Holder[Box[42]])''',
'''read=(items:totaldict<"a" Choice>):>int64=>{
let warm=items["a"]
let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=items["a"] if item isnt? Box return 2 if item.value not=?42 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read(["a"->Box[42]])''',
'''read=(items:array<Choice>):>int64=>{if items.length=?0 return 1
if items[0] isnt? Box return 2
let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=items[0] if item.value not=?42 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read([Box[42]])''',
'''main=():>int64=>{let items:array<Choice>=[Box[42]]
let saved=items[0] items[0]=none
if saved is? Box return saved.value return 1}''',
'''main=():>int64=>{let items:array<Choice>=[Box[42]]
let saved=items[0] if saved is? Box {saved.value=1}
if items[0] is? Box return items[0].value return 2}''',
'''take=(items:array<Choice>):>Choice=>{if items.length=?0 return none
let saved=items[0] return saved}
main=():>int64=>{let items:array<Choice>=[Box[42]]
let saved=take(items) items.clear()
if saved is? Box return saved.value return 1}''',
]]
ERRORS=[HEADER+body for body in [
'''main=():>int64=>{let items:array<Choice>=[Box[42]]
const saved=@items[0] items[0]=none
if saved is? Box return saved.value return 1}''',
'''main=():>int64=>{let items:totaldict<"a" Choice>=["a"->Box[42]]
const saved=@items["a"] items["a"]=none
if saved is? Box return saved.value return 1}''',
]]

CASES += [HEADER+body for body in [
'''consume=(items:array<Choice>):>void=>{items.clear()}
main=():>int64=>{let items:array<Choice>=[Box[42]]
const saved=items[0] consume(items)
if saved is? Box return saved.value return 1}''',
'''read=(items:array<Choice>):>int64=>{if items.length=?0 return 1
let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=items[0] if item isnt? string return 2 if item.length not=?2 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read(["{42}"])''',
'''Holder:type=[choice:Box|array<int64>|none]
read=(holder:Holder):>int64=>{let before=_arena_allocated_bytes let i:int64=0
loop i<?100 {const item=holder.choice if item isnt? array<int64> return 2 if item.length not=?2 return 3 i+=1}
return if _arena_allocated_bytes=?before 42 else 4}
main=():>int64=>read(Holder[[40 2]])''',
'''main=():>int64=>{let items:totaldict<"a" Choice>=["a"->Box[42]]
const saved=items["a"] items["a"]=none
if saved is? Box return saved.value return 1}''',
]]

@pytest.mark.parametrize('source',CASES)
def test_inferred_union_view(source,tmp_path):
    execute(tmp_path,'inferred-union-view',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_required_union_view_conflicts(source):
    with pytest.raises(ReportException):codegen(SrcFile(None,source))

def test_native_inferred_union_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
