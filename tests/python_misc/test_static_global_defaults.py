"""A read-only parameter whose default names a stable `const` global views it.

The global outlives every call, so the omitted default borrows it exactly as
an explicit argument would: no copy is made and neither path releases it."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

VIEWED = '''$explicit_copies
G:type = [edges:array<string> names:dict<string int64>]
const base:G = G[edges=['a' 'b'] names=['a'->1]]
count = (g:G=base):>int64 => g.edges.length + g.names.length
main=():>int64=>{
    let total:int64=0
    let i:int64=0
    loop i <? 100 {total+=count() i+=1}
    let other=G[edges=['x'] names=[]]
    let ok=total =? 300 and count(base) =? 3 and count(other) =? 1 and count() =? 3
    return if ok 42 else 1
}
'''
# Returning the parameter still copies, and a writable global default is
# still the parameter's own copy.
COPIED = '''G:type = [edges:array<string>]
const base:G = G[edges=['a' 'b']]
let mutable:G = G[edges=['m']]
pick = (g:G=base):>G => g
grow = (g:G=mutable):>int64 => {
    mutable.edges.push('n')
    return g.edges.length
}
main=():>int64=>{
    let first=pick()
    first.edges.push('c')
    let again=pick()
    let before=grow()
    let after=grow()
    let ok=first.edges.length =? 3 and again.edges.length =? 2 and base.edges.length =? 2 and before =? 1 and after =? 2
    return if ok 42 else 1
}
'''
CASES = [VIEWED, COPIED]
ERRORS = ['$explicit_copies\n' + COPIED]


@pytest.mark.parametrize('source', CASES)
def test_static_global_defaults(tmp_path, source):
    execute(tmp_path, 'static-default', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_copied_defaults_stay_reported(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_static_global_defaults(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
