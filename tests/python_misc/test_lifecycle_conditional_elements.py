"""Conditional transfers of stable slots preserve sibling owners and cleanup."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

HEADER='''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
consume=(value:Token):>int64=>value.id
'''
CASES = [
    HEADER+'''probe=(flag:bool):>int64=>{let items=[Token[1] Token[2]]
if flag {consume(items[0]);} return items[1].id}
main=():>int64=>{if probe(true) not=?2 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''Pair:type=[left:Token right:Token]
probe=(flag:bool):>int64=>{let items=[Pair[Token[1] Token[2]]]
if flag {consume(items[0].left);} return items[0].right.id}
main=():>int64=>{if probe(true) not=?2 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''probe=(flag:bool):>int64=>{let items=[Token[1] Token[2]]
if flag {consume(items[0]);} items[0]=Token[3] return items[0].id}
main=():>int64=>{if probe(true) not=?3 or trace not=?123 return 1
trace=0 if probe(false) not=?3 or trace not=?123 return 2
return 42}''',
]
CASES.extend([
    HEADER+'''probe=(flag:bool):>int64=>{let items=[[Token[1] Token[2]]]
if flag {consume(items[0][0]);} return items[0][1].id}
main=():>int64=>{if probe(true) not=?2 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''Box:type=[items:array<Token>]
probe=(flag:bool):>int64=>{let box=Box[[Token[1] Token[2]]]
if flag {consume(box.items[0]);} return if box.items.length>?1 box.items[1].id else 0}
main=():>int64=>{if probe(true) not=?2 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
])

CASES.append(HEADER+'''probe=(flag:bool):>void=>{let items=[Token[1] Token[2]]
if flag {consume(items[0]);} else {consume(items[1]);} trace=trace*10+3}
main=():>int64=>{probe(true) if trace not=?132 return 1
trace=0 probe(false) return if trace=?231 42 else 2}''')

MOVE_FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_conditional_element_moves.dewy'
CASES.append(MOVE_FIXTURE.read_text())

ERRORS = [
    HEADER+'''probe=(flag:bool):>int64=>{let items=[Token[1] Token[2]]
if flag {consume(items[0]);} return items[0].id}''',
    HEADER+'''probe=(flag:bool index:int64):>int64=>{let items=[Token[1] Token[2]]
if flag {consume(items[0]);} if index>=?0 and index<?2 return items[index].id
return 42}''',
    HEADER+'''probe=():>int64=>{let items=[Token[1] Token[2]]
loop i in [0..2) {consume(items[0]);} return 42}''',
]

ERRORS.append(HEADER+'''take=(items:array<Token>):>void=>{}
probe=(flag:bool):>int64=>{let items=[Token[1] Token[2]]
if flag {take(items);} return items.length}''')


@pytest.mark.parametrize('source', CASES)
def test_conditional_elements(tmp_path, source):
    execute(tmp_path, 'conditional-elements', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_conditional_element_future_reads_rejected(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_conditional_elements(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
