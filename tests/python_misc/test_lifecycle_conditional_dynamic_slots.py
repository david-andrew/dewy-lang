"""Runtime-selected conditional transfers keep lexical cleanup and saved selectors."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_conditional_dynamic_slot.dewy').read_text()
HEADER = '''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
consume=(value:Token):>int64=>value.id
'''
CASES = [FIXTURE,
    HEADER + '''probe=(flag:bool index:int64):>void=>{
let items=[Token[1] Token[2]]
if index>=?0 and index<?2 {
    if flag {consume(items[index]);} else {consume(items[1-index]);}
}
trace=trace*10+3
}
main=():>int64=>{probe(true 0) if trace not=?132 return 1
trace=0 probe(false 0) return if trace=?231 42 else 2}''',
    HEADER + '''probe=(flag:bool):>void=>{
let items=[Token[1] Token[2]]
let index:int64=0
if flag {consume(items[index]);}
index=1
trace=trace*10+3
}
main=():>int64=>{probe(true) return if trace=?132 42 else 1}''',
    HEADER + '''probe=(items:array<Token> flag:bool index:int64):>void=>{
if flag and index>=?0 and index<?items.length {consume(items[index]);}
trace=trace*10+3
}
main=():>int64=>{probe([Token[1] Token[2]] true 0) if trace not=?132 return 1
trace=0 probe([Token[1] Token[2]] false 0) return if trace=?321 42 else 2}''',
    HEADER + '''probe=(flag:bool index:int64):>void=>{
let items=[Token[1] Token[2]]
loop i in [0..2) {
 if flag and index>=?0 and index<?2 {consume(items[index]);}
 items=[Token[4] Token[5]]
}
}
main=():>int64=>{probe(true 0) return if trace=?124554 42 else 1}''',
    HEADER + '''Box:type=[items:array<Token>]
probe=(flag:bool index:int64):>void=>{
let box=Box[[Token[1] Token[2]]]
if flag and index>=?0 and index<?box.items.length {consume(box.items[index]);}
trace=trace*10+3
}
main=():>int64=>{probe(true 1) if trace not=?231 return 1
trace=0 probe(false 0) return if trace=?321 42 else 2}''',
]
CASES.append(HEADER + """let selections:int64=0
choose=(index:int64):>int64<v=>v>=?0 v=>v<?2>=>{selections+=1 return if index=?0 0 else 1}
probe=(flag:bool index:int64):>void=>{
let items=[Token[1] Token[2]]
if flag {consume(items[choose(index)]);}
trace=trace*10+3
}
main=():>int64=>{probe(true 1) if trace not=?231 or selections not=?1 return 1
trace=0 probe(false 0) return if trace=?321 and selections=?1 42 else 2}""")

CASES.extend([
    HEADER + """Moved=type of [token:Token
$__drop__ release=():>void=>{trace=trace*10+9}
$__move__ relocate=():>Moved=>Moved[Token[4]]]
take=(value:Moved):>void=>{}
probe=(flag:bool index:int64):>void=>{
let items:array<Moved>=[Moved[Token[1]] Moved[Token[2]]]
if flag and index>=?0 and index<?items.length {take(items[index])}
trace=trace*10+3
}
main=():>int64=>{probe(true 0) if trace not=?194392 return 1
trace=0 probe(false 0) return if trace=?39291 42 else 2}""",
    HEADER + """probe=(flag:bool row:int64 column:int64):>void=>{
let items:array<array<Token>>=[[Token[1] Token[2]] [Token[3] Token[4]]]
if flag and row>=?0 and row<?items.length and column>=?0 and column<?items[row].length {consume(items[row][column]);}
trace=trace*10+5
}
main=():>int64=>{probe(true 1 0) if trace not=?35421 return 1
trace=0 probe(false 1 0) return if trace=?54321 42 else 2}""",
])

ERRORS = [HEADER + '''probe=(flag:bool index:int64):>int64=>{
let items=[Token[1] Token[2]]
if flag and index>=?0 and index<?2 {consume(items[index]);}
return items[0].id
}''', HEADER + '''probe=(flag:bool index:int64):>void=>{
let items=[Token[1] Token[2]]
loop i in [0..2) {if flag and index>=?0 and index<?2 {consume(items[index]);}}
}''', HEADER + '''probe=(flag:bool index:int64):>int64=>{
let items=[Token[1] Token[2]]
const view=@items
if flag and index>=?0 and index<?2 {consume(items[index]);}
return view[0].id
}''']


@pytest.mark.parametrize('source', CASES)
def test_conditional_dynamic_slot(tmp_path, source):
    execute(tmp_path, 'conditional-dynamic-slot', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_dynamic_slot_future_uses_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_conditional_dynamic_slots(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
