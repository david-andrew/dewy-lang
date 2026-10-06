"""A last-use record moves into a literal's optional field.

`Applied[state]` stores a record parameter or local into a `State?` field.
At its last use the record is adopted, as a field assignment of a union
with a record member already does, rather than copied.
"""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
State:type=[values:array<int64>]
Applied:type=[state:State? count:int64=0]
apply=(state:State n:int64):>Applied=>{
    let result=Applied[state]
    if n >? 2 {result.state=none}
    return result
}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    let total:int64=0
    let k:int64=0
    loop k <? 100 {
        let s=State[[1 2 3]]
        let a=apply(s k)
        if a.state isnt? none {total+=a.state.values.length}
        k+=1
    }
    return if total=?9 and _arena_live_bytes=?before 42 else 1
}
'''
CASES = [SOURCE]


@pytest.mark.parametrize('source', CASES)
def test_optional_field_literal_moves(tmp_path, source):
    execute(tmp_path, 'optional-field-literal', codegen(SrcFile(None, source), debug_locations=False))


def test_native_optional_field_literal_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
