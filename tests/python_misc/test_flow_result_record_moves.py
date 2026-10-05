"""A record local at its last use moves into a flow result.

`let base = if c right else left` keeps the selected record. When neither
local is read again on that path, the selected arm hands over its handle,
as `let t = x` does; the emptied local releases nothing at scope exit. A
local read again later keeps the copy.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''Shape:type=[constant:int64 items:array<int64>]
make=(n:int64):>Shape=>{
    let items:array<int64>=[]
    let i:int64=0
    loop i <? n {items.push(i) i+=1}
    return Shape[n items]
}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''pick=(n:int64 mul:bool):>int64=>{
    let left=make(n)
    let right=make(n+1)
    if mul {
        let base=if left.items.length=?0 right else left
        let t:int64=0
        loop item in base.items {t+=item}
        return t
    }
    return left.constant+right.constant
}
main=():>int64=>pick(0 true)+pick(3 true)+pick(4 false)+30
'''
READ_AGAIN = PRELUDE + '''pick=(n:int64):>int64=>{
    let left=make(n)
    let right=make(n+1)
    let base=if n >? 2 right else left
    base.items.push(7)
    return base.items.length+left.items.length*10+right.items.length
}
main=():>int64=>pick(3)+3
'''
CASES = [MOVED, READ_AGAIN]
ERRORS = ['$explicit_copies\n' + READ_AGAIN]


@pytest.mark.parametrize('source', CASES)
def test_flow_result_record_moves(tmp_path, source):
    execute(tmp_path, 'flow-moves', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_flow_result_read_again_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_flow_result_record_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
