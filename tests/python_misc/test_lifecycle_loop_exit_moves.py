"""A break has no loop backedge; other continuations retain their owners."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_lifecycle_loop_moves import HEADER

CASES = [
    HEADER+'''probe=():>int64=>{
    let owner=Token[42] let result:int64=0
    loop true {result=consume(owner) break}
    return result
}
main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..20) {if probe() not=?42 return 1}
return if drops=?20 and before=?_arena_live_bytes 42 else 2}''',
    HEADER+'''probe=(flag:bool):>int64=>{
    let owner=Token[42] let result:int64=42
    loop i in [0..4) {
        if i<?2 continue
        if flag {result=consume(owner) break}
    }
    return result
}
main=():>int64=>{let a=probe(true) let b=probe(false)
return if a+b=?84 and drops=?2 42 else 1}''',
    HEADER+'''main=():>int64=>{
    loop i in [0..20) {
        let owner=Token[42]
        loop j in [0..3) {if j=?1 {let moved=owner consume(moved); break}}
    }
    return if drops=?20 42 else 1
}''',
    HEADER+'''probe=(owner:Token):>int64=>{
    let result:int64=0
    loop true {result=consume(owner) break}
    return result
}
main=():>int64=>{let result=probe(Token[42]) return if drops=?1 result else 1}''',
    '''let drops:int64=0 let moves:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{drops+=1}
$__move__ move=():>Token=>{moves+=1 Token[id+1]}]
consume=(owner:Token):>int64=>owner.id
probe=(flag:bool):>int64=>{
    let owner=Token[41] let result:int64=42
    loop i in [0..4) {if flag and i=?2 {result=consume(owner) break}}
    return result
}
main=():>int64=>{let before:int64=_arena_live_bytes
loop i in [0..20) {if probe(i%2=?0) not=?42 return 1}
return if drops=?20 and moves=?10 and before=?_arena_live_bytes 42 else 2}''',
]
CASES += [HEADER+'''probe=():>int64=>{
    let owner=Token[42] let result:int64=0
    $outer
    loop i in [0..3) {loop true {result=consume(owner) break $outer}}
    return result
}
main=():>int64=>{let result=probe() return if drops=?1 result else 1}''']
ERRORS = [
    HEADER+'''main=():>int64=>{let owner=Token[42]
$outer loop i in [0..3) {loop true {consume(owner); continue $outer}} return 42}''',
    HEADER+'''main=():>int64=>{let owner=Token[42]
loop i in [0..3) {consume(owner); continue} return 42}''',
    HEADER+'''main=():>int64=>{let owner=Token[42]
loop true {consume(owner); break} return owner.id}''',
    HEADER+'''main=():>int64=>{let owner=Token[42] let alias=owner
loop true {consume(owner); break} return alias.id}''',
    HEADER+'''main=():>int64=>{let owner=Token[42]
loop i in [0..3) {loop j in [0..2) {consume(owner); break}} return 42}''',
    HEADER+'''main=():>int64=>{let owner=Token[42]
loop i in [0..3) {consume(owner); if i=?1 break} return 42}''',
    HEADER+'''main=():>int64=>{let owner=Token[42]
loop true {consume(owner); loop j in [0..2) {break}} return 42}''',
]

@pytest.mark.parametrize('source', CASES)
def test_resource_move_before_loop_exit(source, tmp_path):
    execute(tmp_path, 'loop-exit-move', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_repeating_or_later_resource_use(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_loop_exit_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
