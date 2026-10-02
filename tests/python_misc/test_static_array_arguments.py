"""A constant literal argument the caller keeps is static data, built once.

`name in? ['push' 'pop']` passes a literal the callee only reads; it no longer
allocates per evaluation. A callee that changes its own copy detaches first,
so the shared static literal never changes. A literal passed to an optional
parameter keeps its wrapping."""
from test_scalar_projection import execute
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile

SOURCE = '''kind=(name:string):>int64=>{
    if name in? ['push' 'pop' 'insert'] return 1
    if name not in? ['a' 'b'] return 2
    return 3
}
digit=(c:int64):>bool=>c in? [48 49 50]
grown=(xs:array<int64>):>int64=>{
    xs.push(9)
    return xs.length
}
optional=(xs:array<int64>|none):>int64=>if xs isnt? none xs.length else 0
main=():>int64=>{
    let total:int64=0
    let i:int64=0
    loop i <? 1000 {
        total+=kind('pop')+kind('a')+kind('zz')
        if digit(49) {total+=1}
        if grown([1 2]) not=? 3 return 1
        if optional([4 5 6]) not=? 3 return 3
        i+=1
    }
    return if total =? 7000 42 else 2
}
'''


def test_static_array_arguments(tmp_path):
    execute(tmp_path, 'static-arrays', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_static_array_arguments(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
