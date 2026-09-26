"""A component may leave its owner on some paths only.

The owner keeps a flag per such component; its cleanup drops the component
only while the flag says it is still held, and a replacement restores it.
"""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

HEADER='''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
Pair:type=[left:Token right:Token]
consume=(value:Token):>int64=>value.id
'''
CASES=[
    HEADER+'''probe=(flag:bool):>int64=>{let pair=Pair[Token[1] Token[2]]
if flag {consume(pair.left);} return pair.right.id}
main=():>int64=>{if probe(true) not=?2 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''probe=(flag:bool):>int64=>{let pair=Pair[Token[1] Token[2]]
if flag {consume(pair.left); return 5} return pair.right.id}
main=():>int64=>{if probe(true) not=?5 or trace not=?12 return 1
trace=0 if probe(false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''probe=(pair:Pair flag:bool):>int64=>{if flag {consume(pair.left);} return pair.right.id}
main=():>int64=>{if probe(Pair[Token[1] Token[2]] true) not=?2 or trace not=?12 return 1
trace=0 if probe(Pair[Token[1] Token[2]] false) not=?2 or trace not=?21 return 2
return 42}''',
    HEADER+'''probe=(flag:bool):>void=>{let pair=Pair[Token[1] Token[2]]
if flag {consume(pair.left);} else {consume(pair.right);} trace=trace*10+3}
main=():>int64=>{probe(true) if trace not=?132 return 1
trace=0 probe(false) return if trace=?231 42 else 2}''',
    HEADER+'''probe=():>int64=>{let pair=Pair[Token[1] Token[2]] let total:int64=0
loop i in [0..3) {if i=?1 {total+=consume(pair.left) break}}
return total+pair.right.id}
main=():>int64=>{if probe() not=?3 or trace not=?12 return 1
return 42}''',
    HEADER+'''Outer:type=[inner:Pair tag:int64]
probe=(flag:bool):>int64=>{let outer=Outer[Pair[Token[1] Token[2]] 4]
if flag {consume(outer.inner.left);} return outer.inner.right.id+outer.tag}
main=():>int64=>{if probe(true) not=?6 or trace not=?12 return 1
trace=0 if probe(false) not=?6 or trace not=?21 return 2
return 42}''',
]
ERRORS=[
    HEADER+'''main=():>int64=>{let pair=Pair[Token[1] Token[2]] if true {consume(pair.left);} return pair.left.id}''',
    HEADER+'''main=():>int64=>{let pair=Pair[Token[1] Token[2]] loop i in [0..2) {consume(pair.left);} return 42}''',
    HEADER+'''keep=(pair:Pair):>int64=>pair.right.id
main=():>int64=>{let pair=Pair[Token[1] Token[2]] if true {consume(pair.left);} return keep(pair)}''',
]
@pytest.mark.parametrize('source', CASES)
def test_conditional_components(tmp_path, source):
    execute(tmp_path, 'conditional-component', codegen(SrcFile(None, source), debug_locations=False))
@pytest.mark.parametrize('source', ERRORS)
def test_later_component_use(source):
    with pytest.raises(ReportException): codegen(SrcFile(None, source))
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_conditional_components.dewy'
def test_conditional_components_kernel(tmp_path):
    execute(tmp_path, 'conditional-component-kernel', codegen(SrcFile.from_path(FIXTURE), debug_locations=False))

def test_native_conditional_components(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[*CASES, FIXTURE.read_text()], errors=ERRORS)
