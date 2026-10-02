"""A loop over `d.get(k default)` views the stored array when the loop cannot
change the dictionary, even if the function writes it elsewhere. A local bound
to such a lookup is a view when nothing during its lifetime can change the
dictionary, including a place parameter that no ambient alias names."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

VIEWED = '''$explicit_copies
R:type = [routes:dict<int64 array<int64>>=[]]
twice=(x:int64):>int64=>x*2
total=(@r:R key:int64):>int64=>{
    r.routes[key+1]=[5]
    let sum:int64=0
    loop item in r.routes.get(key []) {sum+=twice(item)}
    loop item in r.routes.get(key+2 []) {sum+=item}
    return sum
}
main=():>int64=>{
    let r=R[]
    r.routes[1]=[10 11]
    return if total(@r 1) =? 42 42 else 1
}
'''
# Rewriting the entry during the loop still iterates the value on entry.
REWRITTEN = '''R:type = [routes:dict<int64 array<int64>>=[]]
total=(@r:R key:int64):>int64=>{
    let sum:int64=0
    loop item in r.routes.get(key []) {
        sum+=item
        r.routes[key]=[]
    }
    return sum
}
main=():>int64=>{
    let r=R[]
    r.routes[1]=[20 22]
    let sum=total(@r 1)
    let ok=sum =? 42 and r.routes.get(1 []).length =? 0
    return if ok 42 else 1
}
'''
BOUND = '''$explicit_copies
R:type = [routes:dict<int64 array<int64>>=[]]
count=(@r:R key:int64):>int64=>{
    r.routes[key+1]=[5]
    let routes=r.routes.get(key [])
    let sum:int64=0
    loop item in routes {sum+=item}
    r.routes[key+2]=[6]
    return sum
}
main=():>int64=>{
    let r=R[]
    r.routes[1]=[20 22]
    return if count(@r 1) =? 42 42 else 1
}
'''
# A write during the bound lookup's lifetime keeps it an owned copy.
BOUND_WRITTEN = '''R:type = [routes:dict<int64 array<int64>>=[]]
count=(@r:R key:int64):>int64=>{
    let routes=r.routes.get(key [])
    r.routes[key]=[1]
    let sum:int64=0
    loop item in routes {sum+=item}
    return sum
}
main=():>int64=>{
    let r=R[]
    r.routes[1]=[20 22]
    return if count(@r 1) =? 42 42 else 1
}
'''
CASES = [VIEWED, REWRITTEN, BOUND, BOUND_WRITTEN]
ERRORS = ['$explicit_copies\n' + REWRITTEN, '$explicit_copies\n' + BOUND_WRITTEN]


@pytest.mark.parametrize('source', CASES)
def test_get_loop_views(tmp_path, source):
    execute(tmp_path, 'get-loop-view', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_rewritten_get_loop_keeps_its_snapshot(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_get_loop_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
