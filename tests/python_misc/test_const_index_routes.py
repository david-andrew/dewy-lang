"""An immutable selector has one route per execution of its declaration."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

CASES = [
    '''select=(i:int64):>int64=>{
let xs:array<array<int64>>=[[] []]
if i<?0 or i>=?xs.length return 0
const chosen=i
xs[chosen].clear
xs[chosen].push(42)
$assert xs[chosen].length=?1
return xs[chosen][0]
}
main=():>int64=>select(1)''',
    '''select=(i:int64):>int64=>{
let xs:array<array<int64>>=[[] []]
if i<?0 or i>=?xs.length return 0
const chosen=i
xs[chosen].clear xs[chosen].push(42)
let copy=xs
xs[chosen].clear
$assert copy[chosen].length=?1
return copy[chosen][0]
}
main=():>int64=>select(1)''',
    '''main=():>int64=>{
let xs:array<array<int64>>=[[] []]
let i:int64=0
loop i<?xs.length {
const chosen=i
xs[chosen].clear xs[chosen].push(42)
$assert xs[chosen].length=?1
i+=1
}
return 42
}''',
]
CASES.append(CASES[0].replace('array<array<int64>>=[[] []]', 'array<[items:array<int64>]>=[[items=[]] [items=[]]]').replace('xs[chosen]', 'xs[chosen].items'))
ERRORS = [
    '''check=(i:int64 j:int64):>int64=>{
let xs:array<array<int64>>=[[] []]
if i<?0 or i>=?xs.length or j<?0 or j>=?xs.length return 0
const chosen=i const other=j
xs[chosen].clear xs[chosen].push(42)
xs[other].clear
return xs[chosen][0]
}''',
    '''check=(i:int64):>int64=>{
let xs:array<array<int64>>=[[] []]
if i<?0 or i>=?xs.length return 0
const chosen=i
xs[chosen].clear xs[chosen].push(42)
xs=[]
return xs[chosen][0]
}''',
    '''main=():>int64=>{
let xs:array<array<int64>>=[[] []]
let i:int64=0
loop i<?xs.length {
const chosen=i
if i>?0 {$assert xs[chosen].length=?1}
xs[chosen].clear xs[chosen].push(42)
i+=1
}
return 42
}''',
]

@pytest.mark.parametrize('source', CASES)
def test_const_index_route(tmp_path, source):
    execute(tmp_path, 'const-index', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_const_index_routes_invalidate(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_const_index_routes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_const_index_routes_survive_resident_rollback():
    from dewy.semantic import modules
    first = codegen(SrcFile(None, CASES[0]))
    codegen(SrcFile(None, CASES[1]))
    assert codegen(SrcFile(None, CASES[0])) == first
    for resident in modules._resident_preludes.values():
        resident.rollback()
        registry = resident.state['registry']
        assert all(binding in registry.by_id and routes <= registry.route_paths.keys()
                   for binding, routes in registry.index_routes.items())
