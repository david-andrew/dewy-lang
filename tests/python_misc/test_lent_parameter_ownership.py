"""A parameter lent as a place to a call before its final transfer is owned.

The lend ends when the call returns: the callee may change the input but never
keeps an alias of it. A later transfer then consumes the parameter, so callers
donate a dying value instead of the callee copying it on entry."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''Packed:type = [count:int64 items:array<int64>]
trim=(@items:array<int64>):>void=>{if items.length >? 2 {items.truncate(2)}}
fresh=(n:int64):>array<int64>=>{
    let result:array<int64>=[]
    let i:int64=0
    loop i <? n {result.push(i) i+=1}
    return result
}
'''
OWNED = '$explicit_copies\n' + PRELUDE + '''pack=(items:array<int64>):>Packed=>{
    trim(@items)
    if items.length =? 0 return Packed[0 []]
    return Packed[items.length items]
}
main=():>int64=>{
    let packed=pack(fresh(5))
    let empty=pack(fresh(0))
    return if packed.items.length =? 2 and packed.count =? 2 and empty.count =? 0 42 else 1
}
'''
# A local view of the parameter outlives the lend: no ownership transfer.
VIEWED = PRELUDE + '''pack=(items:array<int64>):>Packed=>{
    trim(@items)
    let first=items
    first.push(9)
    return Packed[first.length items]
}
main=():>int64=>{
    let packed=pack(fresh(5))
    return if packed.items.length =? 2 and packed.count =? 3 42 else 1
}
'''
CASES = [OWNED, VIEWED]
ERRORS = ['$explicit_copies\n' + VIEWED]


@pytest.mark.parametrize('source', CASES)
def test_lent_parameter_ownership(tmp_path, source):
    execute(tmp_path, 'lent-ownership', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_aliased_parameter_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_lent_parameter_ownership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
