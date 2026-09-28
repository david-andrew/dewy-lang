"""Family narrowing retains a stable owner through read-only call upcasts."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]
HEADER='''Node=$abstract type of [items:array<int64>]
Leaf=type of Node & [value:int64]
Branch=type of Node & [child:int64]
Other=type of Node & [other:int64]
'''
CASES=[(ROOT/'tests/fixtures/narrowed_record_borrow.dewy').read_text()]
CASES.append(HEADER+'''read=(node:Node ignored:int64):>int64=>{
    if node.items.length=?0 return 1
    return node.items[0]
}
alter=(@node:Node):>int64=>{
    if node.items.length>?0 {node.items[0]=9}
    return 0
}
visit=(node:Node):>int64=>{
    if node is? Leaf|Branch return read(node alter(@node))
    return 1
}
main=():>int64=>visit(Leaf[[42] 1])''')
CASES.append(HEADER+'''read=(before:Node @after:Node):>int64=>{
    if after.items.length>?0 {after.items[0]=9}
    if before.items.length=?0 return 1
    return before.items[0]
}
visit=(node:Node):>int64=>{
    if node is? Leaf|Branch return read(node @node)
    return 1
}
main=():>int64=>visit(Leaf[[42] 1])''')

CASES.append(CASES[1].replace('read(node alter(@node))', 'read((node as Node) alter(@node))'))
CASES.append(CASES[2].replace('read(node @node)', 'read(before=node after=@node)'))

@pytest.mark.parametrize('source', CASES)
def test_narrowed_record_borrow_preserves_snapshot(tmp_path,source):
    execute(tmp_path,'narrowed-record-borrow',codegen(SrcFile(None,source),debug_locations=False))

def test_native_narrowed_record_borrow(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=[])
