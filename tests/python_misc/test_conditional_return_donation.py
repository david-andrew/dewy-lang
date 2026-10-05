"""A parameter returned on one branch is still a single consuming use.

An aggregate input becomes an owning parameter (the caller donates its last
use) when its final read consumes it once. A read inside a conditional
`return` runs at most once and ends its path; the paths that do not take it
release the input. A read inside a loop may run many times, so it keeps
the ordinary copy.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type=[values:array<int64>]
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''pick=(left:State right:State flag:bool):>State=>{
    if flag return right
    return left
}
first=(items:State fallback:State):>State=>{
    if items.values.length >? 0 return items
    return fallback
}
main=():>int64=>{
    let total:int64=0
    loop flag in [true false] {
        let a=State[[1 2]]
        let b=State[[3]]
        let r=pick(a b flag)
        total=total*10+r.values.length
    }
    let empty=State[[]]
    let other=State[[7 8 9]]
    let f=first(empty other)
    return total+f.values.length+27
}
'''
LOOPED = PRELUDE + '''last=(items:State count:int64):>State=>{
    let i:int64=0
    loop i <? count {
        if i =? 3 return items
        i+=1
    }
    return State[[]]
}
main=():>int64=>{
    let a=State[[1 2]]
    let r=last(a 5)
    return r.values.length+40
}
'''
CASES = [MOVED, LOOPED]
ERRORS = ['$explicit_copies\n' + LOOPED]


@pytest.mark.parametrize('source', CASES)
def test_conditional_return_donation(tmp_path, source):
    execute(tmp_path, 'conditional-return', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_looped_return_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_conditional_return_donation(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
