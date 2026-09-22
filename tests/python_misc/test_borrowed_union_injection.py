"""Read-only call conversions may lend payloads through temporary union cells."""

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

HEADER = 'Box:type=[value:int64]\n'
CASES = [HEADER + body for body in [
    '''read=(item:Box?):>int64 & no_effects=>{if item is? none return 0 return item.value}
forward=(item:Box):>int64 & no_effects=>read(item)
main=():>int64=>forward(Box[42])''',
    '''read=(item:Box|string|none):>int64 & no_effects=>{if item is? Box return item.value return 0}
forward=(item:Box|string):>int64 & no_effects=>read(item)
main=():>int64=>forward(Box[42])''',
    '''read=(items:array<int64> | none):>int64 & no_effects=>{if items is? none return 0
if items.length =? 0 return 0 return items[0]}
forward=(items:array<int64>):>int64 & no_effects=>read(items)
main=():>int64=>forward([42])''',
    '''read=(text:string?):>int64 & no_effects=>{if text is? none return 0 return text.length+40}
forward=(text:string):>int64 & no_effects=>read(text)
main=():>int64=>forward("{42}")''',
    '''read=(item:Box?):>int64 & no_effects=>{if item is? none return 0 return item.value}
repeat=(item:Box):>int64 & no_effects=>{loop i in 0..99 {if read(item) not=?42 return 1} return 42}
work=(item:Box):>int64=>{let before=_arena_allocated_bytes let result=repeat(item)
return if _arena_allocated_bytes =? before result else 2}
main=():>int64=>work(Box[42])''',
    '''read=(item:Box? ignored:int64):>int64=>{if item is? none return 0 return item.value}
alter=(@item:Box):>int64=>{item.value=9 return 0}
forward=(item:Box):>int64=>read(item alter(@item))
main=():>int64=>forward(Box[42])''',
]]
# Exercise both normalized keyword calls and explicit source conversions.
CASES += [HEADER + body for body in [
    '''read=(ignored:int64 item:Box?):>int64 & no_effects=>{if item is? none return 0 return item.value+ignored}
forward=(item:Box):>int64 & no_effects=>read(item=item ignored=0)
main=():>int64=>forward(Box[42])''',
    '''read=(item:Box?):>int64 & no_effects=>{if item is? none return 0 return item.value}
forward=(item:Box):>int64 & no_effects=>read(item as Box?)
main=():>int64=>forward(Box[42])''',
    '''read=(item:Box|string|none):>int64 & no_effects=>{if item is? string return item.length+40 return 0}
forward=(item:Box|string):>int64 & no_effects=>read(item)
main=():>int64=>forward("{42}")''',
    '''read=(a:Box? b:Box?):>int64 & no_effects=>{if a is? none or b is? none return 0 return a.value+b.value}
forward=(a:Box b:Box):>int64 & no_effects=>read(a b)
main=():>int64=>forward(Box[20] Box[22])''',
    '''keep=(item:Box?):>Box?=>item
forward=(item:Box):>Box?=>keep(item)
main=():>int64=>{let original=Box[42] let kept=forward(original)
original.value=7 if kept is? none return 1 return kept.value}''',
    '''read=(item:Box?):>int64 & no_effects=>{if item is? none return 0 return item.value}
forward=(items:array<Box>):>int64 & no_effects=>{if items.length=?0 return 0 return read(items[0])}
main=():>int64=>forward([Box[42]])''',
]]
ERRORS = [HEADER + body for body in [
    '''read=(item:Box? ignored:int64):>int64=>{if item is? none return 0 return item.value}
alter=(@item:Box):>int64=>{item.value=9 return 0}
forward=(item:Box):>int64 & no allocates=>read(item alter(@item))''',
    '''mutate=(item:Box?):>int64=>{if item is? none return 0 item.value+=1 return item.value}
forward=(item:Box):>int64 & no allocates=>mutate(item)''',
    '''keep=(item:Box?):>Box?=>item
forward=(item:Box):>Box? & no allocates=>keep(item)''',
    '''forward=(item:Box callback:(value:Box?):>int64 & no_effects):>int64 & no allocates=>callback(item)''',
]]

# Borrowing must not erase resource hooks or bypass an owning result copy.
ERRORS.append('''let copies:int64=0
Token=type of [value:int64
$__copy__ duplicate=():>Token=>{copies+=1 return Token[value]}]
read=(item:Token?):>int64=>{if item is? none return 0 return item.value}
forward=(item:Token):>int64 & no_effects=>read(item)
''')


@pytest.mark.parametrize('source', CASES)
def test_borrowed_union_injection(tmp_path, source):
    execute(tmp_path, 'borrowed-union-injection', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_unsafe_union_injection_does_not_claim_no_allocation(source):
    with pytest.raises(ReportException, match="effect contract"):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_borrowed_union_injection(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
