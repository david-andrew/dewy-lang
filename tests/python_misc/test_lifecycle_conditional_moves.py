"""Logical cleanup follows branch consumption without copying an owner."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

HEADER='''let trace:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
consume=(value:Token):>int64=>value.id
'''
CASES=[
    HEADER+'''probe=(flag:bool):>void=>{let owner=Token[3]
if flag {consume(owner);} trace=trace*10+1}
main=():>int64=>{probe(true) if trace not=?31 return 1
trace=0 probe(false) return if trace=?13 42 else 2}''',
    HEADER+'''probe=(flag:bool):>int64=>{let owner=Token[3]
let result=if flag consume(owner) else consume(owner)
return result}
main=():>int64=>{let a=probe(true) let b=probe(false)
return if trace=?33 and a+b=?6 42 else 1}''',
    HEADER+'''probe=(flag:bool):>void=>{let owner=Token[3]
if flag {let next=owner consume(next);}}
main=():>int64=>{probe(true) probe(false) return if trace=?33 42 else 1}''',
    HEADER+'''probe=(owner:Token flag:bool):>void=>{if flag {consume(owner);} trace=trace*10+1}
main=():>int64=>{probe(Token[3] true) if trace not=?31 return 1
trace=0 probe(Token[3] false) return if trace=?13 42 else 2}''',
]
CASES += [
    HEADER+'''probe=(flag:bool):>int64=>{let owner=Token[3]
let selected=if flag owner else Token[4]
return selected.id}
main=():>int64=>{if probe(true) not=?3 or trace not=?3 return 1
trace=0 if probe(false) not=?4 or trace not=?43 return 2
return 42}''',
    HEADER+'''probe=(flag:bool other:bool):>void=>{let owner=Token[3]
if flag {if other {consume(owner);} else {return}} trace=trace*10+1}
main=():>int64=>{probe(true true) if trace not=?31 return 1
trace=0 probe(true false) if trace not=?3 return 2
trace=0 probe(false true) return if trace=?13 42 else 3}''',
    HEADER+'''probe=(flag:bool):>void=>{let owner=Token[3]
if flag {} else if consume(owner)=?3 {} trace=trace*10+1}
main=():>int64=>{probe(true) if trace not=?13 return 1
trace=0 probe(false) return if trace=?31 42 else 2}''',
    HEADER+'''probe=(flag:bool):>int64=>{let owner=Token[3] let alias=owner
let value=alias.id
if flag {consume(owner);} return value}
main=():>int64=>{let a=probe(true) let b=probe(false)
return if trace=?33 and a+b=?6 42 else 1}''',
    '''let drops:int64=0 let moves:int64=0
Moving=type of [value:int64 values:array<int64>
$__drop__ release=():>void=>{drops+=1 values.clear}
$__move__ relocate=():>Moving=>{moves+=1 Moving[value+1 values.copy()]}]
consume=(item:Moving):>int64=>item.value
probe=(flag:bool):>int64=>{let owner=Moving[41 [1 2 3]]
return if flag consume(owner) else 42}
main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..20) {if probe(i%2=?0) not=?42 return 1}
return if drops=?20 and moves=?10 and before=?_arena_live_bytes 42 else 2}''',
]
ERRORS=[
    HEADER+'''main=():>int64=>{let owner=Token[3] if true {consume(owner);} return owner.id}''',
    HEADER+'''main=():>int64=>{let owner=Token[3] let view=owner
if true {consume(owner);} return view.id}''',
    HEADER+'''main=():>int64=>{let owner=Token[3] loop i in [0..2) {consume(owner);} return 42}''',
    HEADER+'''both=(@a:Token b:Token):>int64=>a.id+b.id
main=():>int64=>{let owner=Token[3] if true {both(@owner owner);} return 42}''',
]
ERRORS += [
    HEADER+'''main=():>int64=>{let owner=Token[3] let alias=owner
let callback=():>int64=>alias.id
if true {consume(owner);} return callback()}''',
    HEADER+'''bad=(flag:bool):>void & no_effects=>{let owner=Token[3] if flag {consume(owner);}}''',
]
@pytest.mark.parametrize('source', CASES)
def test_conditional_ownership(tmp_path,source):
    execute(tmp_path,'conditional-owner',codegen(SrcFile(None,source),debug_locations=False))
@pytest.mark.parametrize('source', ERRORS)
def test_later_or_overlapping_resource_use(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_conditional_moves.dewy'
def test_conditional_ownership_kernel(tmp_path):
    execute(tmp_path, 'conditional-owner-kernel', codegen(SrcFile.from_path(FIXTURE),debug_locations=False))

def test_native_conditional_ownership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=[*CASES,FIXTURE.read_text()],errors=ERRORS)
