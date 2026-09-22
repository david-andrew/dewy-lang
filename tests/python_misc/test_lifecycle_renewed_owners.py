"""A fresh replacement permits another transfer, including across loop backedges."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute
from test_lifecycle_loop_moves import HEADER

CASES=[
    HEADER+'''work=():>int64=>{let owner=Token[1] consume(owner); owner=Token[2]
return if drops=?1 and owner.id=?2 42 else 1}
main=():>int64=>{let result=work() return if drops=?2 result else 2}''',
    HEADER+'''work=(flag:bool):>int64=>{let owner=Token[1]
if flag {consume(owner);} owner=Token[2] return if drops=?1 and owner.id=?2 42 else 1}
main=():>int64=>{if work(true) not=?42 or drops not=?2 return 1
drops=0 if work(false) not=?42 or drops not=?2 return 2 return 42}''',
    HEADER+'''work=():>int64=>{let owner=Token[42]
loop i in [0..20) {if consume(owner) not=?42 return 1 owner=Token[42]}
return if drops=?20 and owner.id=?42 42 else 2}
main=():>int64=>{let before=_arena_live_bytes let result=work()
return if drops=?21 and _arena_live_bytes=?before result else 3}''',
    HEADER+'''work=():>int64=>{let owner=Token[42]
loop i in [0..6) {consume(owner); if i%2=?0 {owner=Token[42] continue} owner=Token[42]}
return if drops=?6 42 else 1}
main=():>int64=>{let result=work() return if drops=?7 result else 2}''',
    HEADER+'''again=(item:Token):>bool=>item.id<?3
work=():>int64=>{let owner=Token[0] let n:int64=0
loop again(owner) {n+=1 owner=Token[n]} return if drops=?4 and n=?3 42 else 1}
main=():>int64=>{let result=work() return if drops=?4 result else 2}''',
    HEADER+'''work=():>int64=>{let owner=Token[42]
loop i in [0..2) {loop j in [0..2) {consume(owner); owner=Token[42]}}
return if drops=?4 42 else 1}
main=():>int64=>{let result=work() return if drops=?5 result else 2}''',
    '''let drops:int64=0 let moves:int64=0
Token=type of [id:int64
$__drop__ release=():>void=>{drops+=1}
$__move__ relocate=():>Token=>{moves+=1 return Token[id+1]}]
consume=(item:Token):>int64=>item.id
work=():>int64=>{let owner=Token[41] loop i in [0..10) {
if consume(owner) not=?42 return 1 owner=Token[41]} return 42}
main=():>int64=>{let result=work() return if drops=?11 and moves=?10 result else 2}''',
]
CASES += [HEADER+'''work=():>int64=>{let owner=Token[42]
$outer loop i in [0..3) {loop true {consume(owner); owner=Token[42] continue $outer}}
return if drops=?3 42 else 1}
main=():>int64=>{let result=work() return if drops=?4 result else 2}''']
CASES += [
    HEADER+'''work=(owner:Token):>int64=>{loop i in [0..3) {consume(owner); owner=Token[42]}
return if drops=?3 and owner.id=?42 42 else 1}
main=():>int64=>{let result=work(Token[42]) return if drops=?4 result else 2}''',
    '''let drops:int64=0 let moves:int64=0
Token=type of [id:int64 values:array<int64>
$__drop__ release=():>void=>{drops+=1 values.clear}
$__move__ relocate=():>Token=>{moves+=1 return Token[id values.copy()]}]
consume=(item:Token):>int64=>item.id
work=():>int64=>{let owner=Token[42 [1 2 3]] loop i in [0..100) {
if consume(owner) not=?42 return 1 owner=Token[42 [1 2 3]]} return 42}
main=():>int64=>{let before=_arena_live_bytes let result=work()
return if drops=?101 and moves=?100 and _arena_live_bytes=?before result else 2}''',
]
ERRORS=[
    HEADER+'''main=():>int64=>{let owner=Token[42]
$outer loop i in [0..3) {loop true {consume(owner); continue $outer} owner=Token[42]} return 42}''',
    HEADER+'main=():>int64=>{let owner=Token[42] loop i in [0..2) {consume(owner); if i=?0 {owner=Token[42]}} return 42}',
    HEADER+'main=():>int64=>{let owner=Token[42] loop i in [0..2) {consume(owner); if i=?0 continue owner=Token[42]} return 42}',
    HEADER+'main=():>int64=>{let owner=Token[42] consume(owner); owner=Token[owner.id] return 42}',
    HEADER+'main=():>int64=>{let owner=Token[42] let alias=owner consume(owner); owner=Token[42] return alias.id}',
    HEADER+'''again=(item:Token):>bool=>item.id<?3
main=():>int64=>{let owner=Token[0] let n:int64=0
loop again(owner) {n+=1 owner=Token[n]} return owner.id}''',
]

@pytest.mark.parametrize('source',CASES)
def test_renewed_owner_can_transfer_again(source,tmp_path):
    execute(tmp_path,'renewed-owner',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_every_advancing_path_needs_a_new_owner(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None,source))

def test_native_renewed_owners(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
