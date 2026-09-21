"""Each loop iteration owns its locals; exits cannot repeat consumption."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
HEADER='''let drops:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{drops+=1}]
consume=(item:Token):>int64=>item.id
'''
CASES=[
    HEADER+'''main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..20) {let owner=Token[42]
if i%2=?0 {consume(owner); if drops not=?i+1 return 1} else {if drops not=?i return 2}}
return if drops=?20 and before=?_arena_live_bytes 42 else 3}''',
    HEADER+'''probe=():>void=>{loop i in [0..6) {let owner=Token[42]
if i%2=?0 {let next=owner consume(next); continue} if i=?5 break}}
main=():>int64=>{probe() return if drops=?6 42 else 1}''',
    HEADER+'''probe=(flag:bool):>int64=>{let owner=Token[42]
loop i in [0..3) {if flag return consume(owner)} return 42}
main=():>int64=>{let before:int64=_arena_live_bytes
if probe(true) not=?42 or probe(false) not=?42 return 1
return if drops=?2 and before=?_arena_live_bytes 42 else 2}''',
    HEADER+'''main=():>int64=>{loop i in [0..3) {let owner=Token[42]
loop j in [0..3) {let nested=Token[42] if i=?j {consume(nested);}}
if i=?1 {consume(owner);}}
return if drops=?12 42 else 1}''',
]
ERRORS=[
    HEADER+'main=():>int64=>{let owner=Token[42] loop i in [0..2) {if i=?1 {consume(owner);}} return 42}',
    HEADER+'main=():>int64=>{loop i in [0..2) {let owner=Token[42] if i=?1 {consume(owner);} let after=owner.id} return 42}',
    HEADER+'main=():>int64=>{loop i in [0..2) {let owner=Token[42] loop j in [0..2) {if j=?1 {consume(owner);}}} return 42}',
]
@pytest.mark.parametrize('source',CASES)
def test_iteration_ownership(tmp_path,source):
    execute(tmp_path,'loop-owners',codegen(SrcFile(None,source),debug_locations=False))
@pytest.mark.parametrize('source',ERRORS)
def test_outer_owners_cannot_repeat_consumption(source):
    with pytest.raises(ReportException): codegen(SrcFile(None,source))
def test_native_loop_ownership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
