"""Container operations keep evaluation effects and storage permissions."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''grow=(@items:array<int64>):>void & reads<items> & mutates<items> & allocates=>{
items.reserve(4) items.push(40) items.insert(2 0)}
main=():>int64=>{let items:array<int64>=[] grow(@items)
if items.length=?2 return items[0]+items[1] return 0}''',
    '''work=():>int64 & allocates=>{let items:array<int64>=[1 2 3]
items.truncate(2) items.clear() items.push(42) return items.pop()}
main=():>int64=>work()''',
    '''read=(table:dict<int64 int64>):>int64 & allocates=>table.get(1 default=42)
main=():>int64=>{let table:dict<int64 int64>=[] return read(table)}''',
    '''read=(@table:dict<int64 int64>):>int64 & reads<table> & allocates=>{
if 1 in? table return table[1] return 0}
main=():>int64=>{let table:dict<int64 int64>=[1->42] return read(@table)}''',
    '''store=(@table:dict<int64 int64>):>void & reads<table> & mutates<table> & allocates=>{table[1]=42}
main=():>int64=>{let table:dict<int64 int64>=[] store(@table)
if 1 in? table return table[1] return 0}''',
    '''work=():>int64 & allocates=>{let table:dict<int64 int64>=[1->0]
table.clear() table[1]=42 return table.pop(1)}
main=():>int64=>work()''',
    '''sum=(items:array<int64>):>int64 & allocates=>{let total:int64=0
loop value in items {total+=value} return total}
main=():>int64=>sum([40 2])''',
    '''work=():>int64 & allocates=>{let table:dict<int64 int64>=[1->20 2->22]
let values=table.values let total:int64=0 loop value in values {total+=value}
return total}
main=():>int64=>work()''',
    '''read=(@table:dict<int64 int64>):>int64=>{if 1 in? table return table[1] return 0}
wrap=(@values:dict<int64 int64>):>int64 & reads<values> & allocates=>read(@values)
main=():>int64=>{let values:dict<int64 int64>=[1->42] return wrap(@values)}''',
    '''main=():>int64 & allocates=>{let values:set<int64>=set[1]
values.push(2) values.pop(1); return if 2 in? values 42 else 0}''',
]
ERRORS = [
    # Taking an entry address still searches its dictionary, even when the
    # callee only writes the payload and membership follows from totality.
    """Box:type=[value:int64]
bad=(@table:totaldict<'a'|'b' Box>):>void & mutates<table> & allocates & no reads<table>=>{
let entry=@table['a'] entry.value=42}""",

    '''bad=(@items:array<int64>):>void & reads<items> & allocates=>items.push(42)''',
    '''bad=(@items:array<int64>):>void & mutates<items> & no allocates=>items.push(42)''',
    '''bad=(@table:dict<int64 int64>):>void & reads<table> & allocates=>{table[1]=42}''',
    '''bad=(@table:dict<int64 int64>):>int64 & allocates=>table.get(1 default=42)''',
    '''bad=(table:dict<int64 int64>):>int64 & no_effects=>table.get(1 default=42)''',
    '''let changed:int64=0
fallback=():>int64=>{changed=1 return 0}
bad=(table:dict<int64 int64>):>int64 & allocates=>table.get(1 default=fallback())''',
    '''let changed:int64=0
key=():>int64=>{changed=1 return 1}
bad=(table:dict<int64 int64>):>bool & allocates=>key() in? table''',
    '''let changed:int64=0
select=():>int64=>{changed=1 return 0}
bad=(@arrays:array<array<int64 length=1> length=1>):>void & reads<arrays> & mutates<arrays> & allocates=>arrays[select()].clear()''',
    # A sort key is an actual call, not just evaluation of a function handle.
    '''let changed:int64=0
key=(value:int64):>int64=>{changed+=1 return value}
bad=(@items:array<int64>):>void & reads<items> & mutates<items> & allocates=>items.sort(key=@key)''',
    '''let drops:int64=0
Handle=type of [value:int64
$__drop__ release=():>void=>{drops+=1}]
bad=():>void & allocates=>{let values:array<Handle>=[Handle[1]] values.clear()}''',
]

@pytest.mark.parametrize('source', CASES)
def test_container_effect_contracts(tmp_path, source):
    execute(tmp_path, 'container-effect-contract', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_container_effect_contracts_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_container_effect_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
