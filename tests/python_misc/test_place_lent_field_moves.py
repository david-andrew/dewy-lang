"""A field of a place-lent local moves at its last use.

A place lent to a call ends when the call returns. Only a use inside a call
that also lends the local must stay a copy: the callee would otherwise see
the emptied field."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

MOVED = '''$explicit_copies
W:type = [bytes:array<uint8> failed:bool=false]
fill=(@w:W):>void=>{w.bytes.push(1) w.bytes.push(2)}
make=(fail:bool):>array<uint8>|int64=>{
    let w=W[bytes=[]]
    fill(@w)
    if fail {w.failed=true}
    if w.failed return 0
    return w.bytes
}
plain=():>array<uint8>=>{
    let w=W[bytes=[]]
    fill(@w)
    return w.bytes
}
main=():>int64=>{
    let made=make(false)
    let failed=make(true)
    let ok=made isnt? int64 and made.length =? 2 and failed is? int64 and plain().length =? 2
    return if ok 42 else 1
}
'''
# The same call lends `w` and reads its field: the field stays in place. The
# pushes give it arena storage, which a move would transfer directly.
CONFLICT = '''W:type = [bytes:array<uint8>]
G:type = [first:array<uint8>]
take=(@w:W group:G):>int64=>{
    w.bytes.push(2)
    return group.first.length*10+w.bytes.length
}
main=():>int64=>{
    let w=W[bytes=[]]
    w.bytes.push(1) w.bytes.push(1)
    return if take(@w G[w.bytes]) =? 23 42 else 1
}
'''
CASES = [MOVED, CONFLICT]
ERRORS = ['$explicit_copies\n' + CONFLICT]


@pytest.mark.parametrize('source', CASES)
def test_place_lent_field_moves(tmp_path, source):
    execute(tmp_path, 'lent-field-move', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_same_call_lend_keeps_the_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_place_lent_field_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
