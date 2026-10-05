"""`x = f(x)` moves x into the call, in a loop too.

The assignment replaces x once its value is computed, so the call's read is
the last use of the old value when nothing else reads x before the store.
The next loop iteration reads the replacement. An input the callee changes
in place (`xs.push(n)`) before returning it is still donated: the change
keeps no alias. A read of x after the transfer in the same value keeps the
copy.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

PRELUDE = '''Bag:type=[items:array<int64> total:int64=0]
grow=(xs:array<int64> n:int64):>array<int64>=>{
    xs.push(n)
    return xs
}
add=(bag:Bag n:int64):>Bag=>{
    bag.items.push(n)
    bag.total+=n
    return bag
}
'''
MOVED = '$explicit_copies\n' + PRELUDE + '''main=():>int64=>{
    let xs:array<int64>=[]
    let bag=Bag[[]]
    let i:int64=0
    loop i <? 5 {
        xs=grow(xs i)
        bag=add(bag i)
        i+=1
    }
    let kept=bag.copy()
    bag=add(bag 7)
    return xs.length+bag.total+bag.items.length+kept.items.length+9
}
'''
# `xs.length` reads the old value after the call argument took it.
READ_AFTER = PRELUDE + '''main=():>int64=>{
    let xs:array<int64>=[1]
    let i:int64=0
    loop i <? 3 {
        xs=grow(xs xs.length)
        i+=1
    }
    let t:int64=0
    loop v in xs {t+=v}
    return xs.length*10+t-5
}
'''
CASES = [MOVED, READ_AFTER]
ERRORS = ['$explicit_copies\n' + READ_AFTER]


@pytest.mark.parametrize('source', CASES)
def test_rebinding_moves(tmp_path, source):
    execute(tmp_path, 'rebinding-moves', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_read_after_transfer_keeps_its_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_rebinding_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
