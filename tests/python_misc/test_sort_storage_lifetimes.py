"""A key callback cannot invalidate the receiver while a sort holds it."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''let calls:int64=0
key=(value:int64):>int64=>{calls+=1 return value}
main=():>int64=>{let items:array<int64>=[42 1] items.sort(key=@key)
return if calls=?2 items[1] else 0}''',
    '''sort=(key:(value:int64):>int64):>int64=>{
let items:array<int64>=[42 1] items.sort(key=@key) return items[1]}
main=():>int64=>sort((value:int64):>int64=>value)''',
    '''sort=(@items:array<int64> key:(value:int64):>int64 & no_effects):>void=>items.sort(key=@key)
main=():>int64=>{let items:array<int64>=[42 1]
sort(@items (value:int64):>int64 & no_effects=>value)
return if items.length>?1 items[1] else 0}''',
    '''let items:array<int64>=[42 1]
key=(value:int64):>int64=>{items.clear return value}
sort=(owned:array<int64>):>int64=>{owned.sort(key=@key) return if owned.length>?1 owned[1] else 0}
main=():>int64=>{let result=sort(items) return if items.length=?0 result else 1}''',
    '''Item:type=[rank:int64]
key=(item:Item):>int64=>{item.rank+=1 return item.rank}
main=():>int64=>{let items:array<Item>=[Item[42] Item[1]]
items.sort(key=@key) return items[1].rank}''',


]
ERRORS = [
    '''let items:array<int64>=[42 1]
key=(value:int64):>int64=>{items.clear return value}
main=():>int64=>{items.sort(key=@key) return 42}''',
    '''let items:array<int64>=[42 1]
change=():>void=>items.clear
key=(value:int64):>int64=>{change() return value}
main=():>int64=>{items.sort(key=@key) return 42}''',
    '''let items:array<int64>=[42 1]
key=(value:int64):>int64=>{items.clear return value}
sort=(@target:array<int64>):>void=>target.sort(key=@key)
main=():>int64=>{sort(@items) return 42}''',
    '''let items:array<int64>=[42 1]
key=(value:int64):>int64 & no_effects=>value
direction=():>bool=>{items.clear return false}
main=():>int64=>{items.sort(key=@key reverse=direction()) return 42}''',
    '''sort=(@items:array<int64> key:(value:int64):>int64):>void=>items.sort(key=@key)''',
    '''main=():>int64=>{
let items:array<int64>=[42 1]
let key=(value:int64):>int64=>{items.clear return value}
items.sort(key=@key) return 42}''',
    '''Box:type=[items:array<int64>]
let box=Box[[42 1]]
key=(value:int64):>int64=>{box.items.clear return value}
main=():>int64=>{box.items.sort(key=@key) return 42}''',

]

@pytest.mark.parametrize('source', CASES)
def test_sort_storage_lifetime_executes(tmp_path, source):
    execute(tmp_path, 'sort-storage', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_sort_storage_lifetime_rejected(source):
    with pytest.raises(ReportException, match='sort (key|option) may change its receiver'):
        codegen(SrcFile(None, source))

def test_native_sort_storage_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
