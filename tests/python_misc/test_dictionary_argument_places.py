"""Select proven dictionary entries before applying a call's write barrier."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<string int64>=['x'->0]
set(@table['x']) return table['x']}''',
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<string int64>=['x'->0]
set(value=@(table['x'])) return table['x']}''',
    '''Box:type=[items:array<int64>]
set=(@box:Box):>void=>{box.items.push(42)}
work=(@table:dict<string Box> key:string):>int64=>{
if key not in? table {table[key]=Box[[]]}
set(@table[key]) let entry=@table[key]
return if entry.items.length>?0 entry.items[0] else 1}
main=():>int64=>{let table:dict<string Box>=[] return work(@table 'x')}''',
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<string int64>=['x'->0]
let saved=table set(@table['x']) return if saved['x']=?0 table['x'] else 1}''',
    '''let calls:int64=0
key=():>'x'=>{calls+=1 return 'x'}
set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:totaldict<'x'|'y' int64>=['x'->0 'y'->0]
set(@table[key()]) return if calls=?1 table['x'] else 1}''',
    '''set=(@value:int64?):>void=>{value=42}
main=():>int64=>{let table:dict<string int64?>=['x'->none]
set(@table['x']) return if table['x'] isnt? none table['x'] else 1}''',
    """$explicit_copies
Box:type=[items:array<int64>]
set=(@box:Box):>void=>{box.items.push(42)}
main=():>int64=>{let table:dict<string Box>=['x'->Box[[]]]
let saved=table.copy() set(@table['x'])
let changed=@table['x']
let original=@saved['x']
return if changed.items.length=?1 and original.items.length=?0 changed.items[0] else 1}""",
    """set=(@value:int64 other:int64):>void=>{value=other}
read=():>int64=>42
main=():>int64=>{let table:dict<string int64>=['x'->0]
set(@table['x'] read()) return table['x']}""",

]
ERRORS = [
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<string int64>=[] set(@table['x']) return 42}''',
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{const table:dict<string int64>=['x'->0] set(@table['x']) return 42}''',
    '''both=(@left:int64 @right:int64):>void=>{left=1 right=2}
main=():>int64=>{let table:dict<string int64>=['x'->0] both(@table['x'] @table['x']) return 42}''',
    '''set=(@value:int64):>void=>{value=-1}
main=():>int64=>{let table:dict<string int64<v=>v>=?0>>=['x'->0] set(@table['x']) return 42}''',
    '''Box:type=const [table:dict<string int64>]
set=(@value:int64):>void=>{value=42}
main=():>int64=>{let box=Box[['x'->0]] set(@box.table['x']) return 42}''',
    '''set=(@value:int64):>void=>{value=0}
main=():>int64=>{let table:dict<string int64>=['x'->2]
if table['x'] not=?0 {set(@table['x']) return 84//table['x']} return 42}''',
    """clear=(@table:dict<string int64>):>int64=>{table.clear return 1}
set=(@value:int64 ignored:int64):>void=>{value=42}
main=():>int64=>{let table:dict<string int64>=['x'->0]
set(@table['x'] clear(@table)) return 42}""",
    """let table:dict<string int64>=['x'->0]
clear=():>int64=>{table.clear return 1}
set=(@value:int64 ignored:int64):>void=>{value=42}
main=():>int64=>{if 'x' in? table {set(@table['x'] clear())} return 42}""",

    """let table:dict<string int64>=['x'->0]
set=(@value:int64):>void=>{table.clear value=42}
main=():>int64=>{if 'x' in? table {set(@table['x'])} return 42}""",
    """let table:dict<string int64>=['x'->0]
clear=():>void=>table.clear
set=(@value:int64):>void=>{clear() value=42}
main=():>int64=>{if 'x' in? table {set(@table['x'])} return 42}""",

]

@pytest.mark.parametrize('source', CASES)
def test_dictionary_argument_places(tmp_path, source):
    execute(tmp_path, 'dictionary-argument-place', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_dictionary_argument_places_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_dictionary_argument_places(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
