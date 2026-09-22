"""Nested scalar records share the same bounded, nonescaping frame proof."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PREFIX = '''Point=type of [x:int64 y:int64]
Box=type of [point:Point count:uint8]
'''
CASES = [
    PREFIX + '''work=(n:int64):>int64 & no_effects=>{
let box=Box[Point[n 1] 2] box.point.x+=box.point.y return box.point.x+(box.count as int64)}
main=():>int64=>{let before=_arena_allocated_bytes let result=work(39)
return if _arena_allocated_bytes=?before result else 1}''',
    PREFIX + '''work=():>int64 & no_effects=>{
let total:int64=0 loop i in 0.. and i<?100000 {
let box=Box[Point[i 2] 1] box.point.x=box.point.y+1 total+=box.point.x}
return total}
main=():>int64=>{let before=_arena_allocated_bytes let result=work()
return if result=?300000 and _arena_allocated_bytes=?before 42 else 1}''',
    PREFIX + '''change=(@value:Box):>int64=>{value.point.x+=value.point.y return value.point.x}
work=():>int64 & no_effects=>{let box=Box[Point[40 2] 1] return change(@box)}
main=():>int64=>{let before=_arena_allocated_bytes let result=work()
return if _arena_allocated_bytes=?before result else 1}''',
    PREFIX + '''read=(value:Box):>int64=>value.point.x+value.point.y
work=():>int64 & no_effects=>{let box=Box[Point[40 2] 1] return read(box)}
main=():>int64=>{let before=_arena_allocated_bytes let result=work()
return if _arena_allocated_bytes=?before result else 1}''',
]
CASES += [
    '''Leaf:type=[value:uint8 flag:bool]
Pair:type=[a:Leaf b:Leaf]
Tree:type=[pair:Pair ignored:int64]
work=():>int64 & no_effects=>{let tree=Tree[Pair[Leaf[20 true] Leaf[22 false]] 0]
return (tree.pair.a.value as int64)+(tree.pair.b.value as int64)}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    PREFIX + '''Row:type=const [first:Point second:Point=Point[first.x+2 first.y]]
work=():>int64=>{let row=Row[Point[20 0]] return row.first.x+row.second.x}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
]
ERRORS = [
    PREFIX + 'work=():>Box & no allocates=>{let box=Box[Point[40 2] 1] return box}',
    PREFIX + 'work=():>int64 & no allocates=>{let box=Box[Point[40 2] 1] let saved=box saved.point.x=0 return box.point.x}',
    '''Leaf:type=[text:string]
Root:type=[leaf:Leaf]
work=(s:string):>int64 & no allocates=>{let root=Root[Leaf[s]] return root.leaf.text.length}''',
]

@pytest.mark.parametrize('source', CASES)
def test_nested_record_uses_frame_storage(source, tmp_path):
    execute(tmp_path, 'nested-frame', codegen(SrcFile(None, source)))

@pytest.mark.parametrize('source', ERRORS)
def test_nested_frame_proof_excludes_escapes_and_dynamic_storage(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))

def test_native_nested_frame_records(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_nested_record_budget_counts_repeated_shapes():
    from dewy.semantic import placement, ty
    leaf = ty.ObjectType((ty.ObjectField('value', 'int64'),))
    shape = leaf
    for _ in range(9):
        shape = ty.ObjectType((ty.ObjectField('a', shape), ty.ObjectField('b', shape)))
    assert placement.scalar_record_size(leaf) == 16
    assert placement.scalar_record_size(shape) is None
