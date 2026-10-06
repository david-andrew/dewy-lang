"""Reading scalar elements of an input does not keep it from being donated.

`args[i]` copies a word out of the array: like `args.length`, it inspects
the input without keeping an alias. A parameter that is only inspected and
changed in place before its final store is still an owning input, so the
caller's last use moves into it.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Call:type=[args:array<int64> total:int64]
wrap=(args:array<int64>):>Call=>{
    let total:int64=0
    loop i in 0.. and i <? args.length {
        let value=args[i]
        total+=value
        if value <? 0 {args[i]=0}
    }
    return Call[args total]
}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    let sum:int64=0
    let k:int64=0
    loop k <? 50 {
        let xs:array<int64>=[]
        xs.push(1) xs.push(-2) xs.push(3)
        let call=wrap(xs)
        sum+=call.total
        loop value in call.args {sum+=value}
        k+=1
    }
    return if sum=?300 and _arena_live_bytes=?before 42 else 1
}
'''
CASES = [SOURCE]


@pytest.mark.parametrize('source', CASES)
def test_element_read_donation(tmp_path, source):
    execute(tmp_path, 'element-read-donation', codegen(SrcFile(None, source), debug_locations=False))


def test_native_element_read_donation(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
