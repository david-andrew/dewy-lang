"""A parameter transferred inside early `return`s and again at its final read
is consumed on every path, so the function owns it.

Each early return ends its path before the final read. Ownership is not taken
when an exit before the final read drops the parameter (a donation there would
only be released), and two reads inside one `return` still conflict."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''State:type = [values:array<int64>]
Transfer:type = [normal:State count:int64=0]
grow=(state:State):>Transfer=>Transfer[state 1]
fresh=(n:int64):>State=>{
    let values:array<int64>=[]
    let i:int64=0
    loop i <? n {values.push(i) i+=1}
    return State[values]
}
'''
OWNED = '$explicit_copies\n' + PRELUDE + '''step=(state:State quick:bool):>Transfer=>{
    if quick return grow(state)
    let result=grow(state)
    result.count+=1
    return result
}
# Unchanged early returns, then a final transfer.
keep=(state:State limit:int64):>State=>{
    if limit <? 0 return state
    if limit >? 10 return state
    let result=state
    result.values.push(limit)
    return result
}
main=():>int64=>{
    let a=step(fresh(3) true)
    let b=step(fresh(4) false)
    let c=keep(fresh(2) 5)
    let d=keep(fresh(2) (-1))
    let ok=a.normal.values.length =? 3 and a.count =? 1 and b.normal.values.length =? 4 and b.count =? 2 and c.values.length =? 3 and d.values.length =? 2
    return if ok 42 else 1
}
'''
# An exit that drops the parameter before its final read keeps it borrowed:
# the stores below copy it.
DROPPING = PRELUDE + '''cached=(state:State hit:bool):>Transfer=>{
    if hit return Transfer[State[[]] 0]
    if state.values.length =? 0 return Transfer[state 1]
    return Transfer[state 2]
}
main=():>int64=>if cached(fresh(3) false).count =? 2 42 else 1
'''
SAME_RETURN = PRELUDE + '''both=(state:State):>int64=>{
    return grow(state).normal.values.length + grow(state).normal.values.length
}
main=():>int64=>if both(fresh(3)) =? 6 42 else 1
'''
CASES = [OWNED, DROPPING, SAME_RETURN]
ERRORS = ['$explicit_copies\n' + DROPPING, '$explicit_copies\n' + SAME_RETURN]


@pytest.mark.parametrize('source', CASES)
def test_returning_parameter_transfers(tmp_path, source):
    execute(tmp_path, 'returning-transfer', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_unowned_parameters_keep_their_copies(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_returning_parameter_transfers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
