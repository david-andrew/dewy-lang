"""Entry places capture keys and borrow their dictionary's live storage."""
from pathlib import Path

import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    (Path(__file__).resolve().parents[1] / 'fixtures/dictionary_local_places.dewy').read_text(),
    '''main=():>int64=>{let table:dict<string int64>=['a'->40]
let entry=@table['a'] entry+=2 return table['a']}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0 2->0]
let key:int64=1
if key in? table {let entry=@table[key] key=2 entry=42 return table[1]}
return 0}''',
    '''let calls:int64=0
key=():>'a'=>{calls+=1 return 'a'}
main=():>int64=>{let table:totaldict<'a'|'b' int64>=['a'->40 'b'->0]
let entry=@table[key()] entry+=1 entry+=1
return if calls=?1 table['a'] else 0}''',
    '''set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] set(@entry) return table[1]}''',
    '''Box:type=[value:int64]
main=():>int64=>{let table:dict<int64 Box>=[1->Box[40]]
let entry=@table[1] entry.value+=2 return table[1].value}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] let other=@entry other=42 return table[1]}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] entry=1 table.clear() table[1]=42 return table[1]}''',
    '''main=():>int64=>{let table:totaldict<'a'|'b' int64>=['a'->0 'b'->0]
loop i in [0..2) {let entry=@table['a'] entry+=21}
return table['a']}''',
]
CASES += [
    """$explicit_copies
main=():>int64=>{let table:dict<int64 int64>=[1->40]
let entry=@table[1] entry+=2 return table[1]}""",
    """main=():>int64=>{let table:dict<int64 int64>=[1->42]
let entry=@table[1]
let answer:int64<v=>v=?entry>=table[1]
return answer}""",

    """Box:type=[value:int64]
main=():>int64=>{let table:dict<int64 Box?>=[1->Box[0]]
let saved=table let entry=@table[1]
if entry isnt? none {entry.value=42
if saved[1] isnt? none and saved[1].value=?0 and entry isnt? none return entry.value}
return 0}""",

    """main=():>int64=>{let table:dict<int64 array<int64>>=[1->[0]]
let saved=table let entry=@table[1] entry.push(42)
if entry.length>?1 and saved[1].length=?1 return entry[1]
return 0}""",

    """set=(@value:int64):>void=>{value=42}
main=():>int64=>{let table:dict<int64 int64>=[1->0]
let saved=table
let entry=@table[1] set(@entry) return if saved[1]=?0 table[1] else 0}""",
    """Box:type=[value:int64]
main=():>int64=>{let table:dict<int64 Box>=[1->Box[0]]
let saved=table
let entry=@table[1] entry.value=42 return if saved[1].value=?0 table[1].value else 0}""",

    # Saving a value keeps ordinary value semantics across entry mutation.
    """main=():>int64=>{let table:dict<int64 int64>=[1->40]
let saved=table
let entry=@table[1] entry=42
return if saved[1]=?40 table[1] else 0}""",
    """let drops:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{drops+=1}]
probe=():>int64=>{let table:dict<int64 Handle>=[1->Handle[0]]
let entry=@table[1] entry=Handle[42] return table[1].id}
main=():>int64=>{let answer=probe() return if drops=?2 answer else 0}""",
    """main=():>int64=>{let tables:array<dict<int64 int64>>=[[1->0] [1->0]]
const i=0
if 1 in? tables[i] {let entry=@(tables[i][1]) entry=42 return entry} return 0}""",
    """main=():>int64=>{let table:dict<int64 int64>=[1->2]
let entry=@table[1]
if entry=?0 return 0
return 84//entry}""",
    """main=():>int64=>{let table:dict<int64 array<int64>>=[1->[0]]
let entry=@table[1] entry.push(42)
if entry.length>?1 return entry[1]
return 0}""",
    """main=():>int64=>{let table:dict<int64 int64>=[1->21 2->21]
let answer:int64=0
loop key in [1 2] {if key in? table {let entry=@table[key] answer+=entry}}
return answer}""",
]
ERRORS = [
    # A write through the alias invalidates direct entry facts and vice versa.
    """main=():>int64=>{let table:dict<int64 int64>=[1->1]
let entry=@table[1]
if table[1] not=?0 {entry=0 return 84//table[1]} return 0}""",
    """main=():>int64=>{let table:dict<int64 int64>=[1->1]
let entry=@table[1]
if entry not=?0 {table[1]=0 return 84//entry} return 0}""",
    """Box:type=const [table:dict<int64 int64>]
main=():>int64=>{let box=Box[[1->0]] let entry=@box.table[1] entry=42 return 42}""",
    """main=():>int64=>{let table:dict<int64 int64>=[1->1]
let entry=@table[1] read=():>int64=>entry
entry=42 return read()}""",
    # A captured key is reinitialized on the next iteration; old entry facts
    # do not apply to that iteration's newly selected entry.
    """main=():>int64=>{let table:dict<int64 int64>=[1->1 2->0]
loop key in [1 2] {if key in? table {let entry=@table[key]
if key=?1 {$unsafe_assume entry not=?0} else {return 84//entry}}} return 0}""",

    '''main=():>int64=>{let table:dict<int64 int64>=[]
let unused=@table[1] return 42}''',
    '''main=():>int64=>{const table:dict<int64 int64>=[1->0]
let entry=@table[1] entry=42 return table[1]}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] table.clear() entry=42 return 42}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] table.pop(1) entry=42 return 42}''',
    '''main=():>int64=>{let table:dict<int64 int64>=[1->0]
let entry=@table[1] let other=@entry table[1]=1 other=42 return 42}''',
    '''main=():>int64=>{let table:dict<int64 int64<v=>v>=?0>>=[1->0]
let entry=@table[1] entry=-1 return 42}''',
    '''bad=(@table:dict<int64 int64>):>void & no_effects=>{
if 1 in? table {let entry=@table[1] entry=42}}''',
]

@pytest.mark.parametrize('source', CASES)
def test_dictionary_local_places(tmp_path, source):
    execute(tmp_path, 'dictionary-local-place', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_dictionary_local_places_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_dictionary_local_places(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
