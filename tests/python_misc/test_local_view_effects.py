"""Allocation contracts and lowering consume the same local-view evidence."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile,ReportException
from test_scalar_projection import execute

HEADER='Box:type=[value:int64]\nChoice:type=Box|string|none\n'
CASES=[HEADER+body for body in [
    '''read=(items:array<Choice>):>int64 & no_effects=>{
if items.length=?0 return 1 let item=items[0]
if item is? Box return item.value return 2}
main=():>int64=>read([Box[42]])''',
    '''read=(items:array<Box|none>):>int64 & no allocates=>{
if items.length=?0 return 1 const item=items[0]
if item isnt? none return item.value return 2}
main=():>int64=>read([Box[42]])''',
    '''Holder:type=[choice:Choice]
read=(holder:Holder):>int64 & no_effects=>{let item=holder.choice
if item is? Box return item.value return 2}
main=():>int64=>read(Holder[Box[42]])''',
    '''read=(items:array<Box>):>int64 & no_effects=>{
if items.length=?0 return 1 const item=items[0] return item.value}
main=():>int64=>read([Box[42]])''',
    '''read=(rows:array<array<int64>>):>int64 & no_effects=>{
if rows.length=?0 return 1 let row=rows[0]
if row.length=?0 return 2 return row[0]}
main=():>int64=>read([[42]])''',
    '''read=(items:array<Choice>):>int64 & no_effects=>{
if items.length=?0 return 1 let i:int64=0
loop i<?100 {const item=items[0] if item isnt? Box return 2 if item.value not=?42 return 3 i+=1}
return 42}
main=():>int64=>read([Box[42]])''',
    '''read=(items:array<Box>):>int64 & no allocates=>{
if items.length=?0 return 1 let item=items[0].copy() return item.value}
main=():>int64=>read([Box[42]])''',
    '''read=(items:array<Box>):>int64 & no allocates=>{
if items.length=?0 return 1 let item=items[0] const alias=@item
return alias.value}
main=():>int64=>read([Box[42]])''',
    '''read=(items:array<Choice>):>int64 & no_effects=>{
if items.length=?0 return 1 let item=items[0]
if item is? Box return item.value return 2}
work=(items:array<Choice>):>int64=>{let before=_arena_allocated_bytes let result=read(items)
return if before=?_arena_allocated_bytes result else 3}
main=():>int64=>work([Box[42]])''',
]]

ERRORS=[HEADER+body for body in [
    '''read=(items:array<Choice>):>int64 & no allocates=>{
if items.length=?0 return 1 let item=items[0]
if item is? Box {item.value=42 return item.value} return 2}''',
    '''read=(items:array<Choice>):>int64 & no allocates=>{
if items.length=?0 return 1 let item=items[0] items[0]=none
if item is? Box return item.value return 2}''',
    '''read=(items:array<Choice>):>Choice & no allocates=>{
if items.length=?0 return none let item=items[0] return item}''',
    '''read=(items:array<Choice> f:():>void & no_effects):>int64 & no allocates=>{
if items.length=?0 return 1 let item=items[0] f()
if item is? Box return item.value return 2}''',
    '''read=(items:array<array<int64>>):>int64 & no allocates=>{
if items.length=?0 return 1 let row=items[0].copy()
if row.length=?0 return 2 return row[0]}''',
]]


CASES += ['''read=(items:array<string>):>int64 & no_effects=>{
if items.length=?0 return 1 let text=items[0] return text.length+40}
work=(items:array<string>):>int64=>{let before=_arena_allocated_bytes let value=read(items)
return if _arena_allocated_bytes=?before value else 2}
main=():>int64=>work(["{42}"])''',
'''Holder:type=[text:string]
read=(holder:Holder):>int64 & no_effects=>{const text=holder.text return text.length+40}
work=(holder:Holder):>int64=>{let before=_arena_allocated_bytes let value=read(holder)
return if _arena_allocated_bytes=?before value else 2}
main=():>int64=>work(Holder["{42}"])''',
'''take=(items:array<string>):>string=>{if items.length=?0 return ""
const text=items[0] return text}
main=():>int64=>{let items:array<string>=["{42}"] let saved=take(items)
items.clear() return if saved=?"42" 42 else 1}''']
ERRORS += ['''take=(items:array<string>):>string & no allocates=>{
if items.length=?0 return "" const text=items[0] return text}''']

@pytest.mark.parametrize('source',CASES)
def test_shared_local_view_allocation_proof(source,tmp_path):
    execute(tmp_path,'local-view-effect',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_local_view_needs_complete_storage_proof(source):
    with pytest.raises(ReportException):codegen(SrcFile(None,source))

def test_native_local_view_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
