"""A getter's element view survives appends to its array, and only appends."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]
HEADER='''Node:type = [items:array<int64> value:int64]
node_at=(nodes:array<Node> id:addr<i => i <? nodes.length>):>Node=>nodes[id].copy()
'''
WALK='''walk=(@nodes:array<Node>):>int64=>{
    if nodes.length =? 0 return 3
    let node=node_at(nodes 0)
    change(@nodes)
    return node.value+node.items.length
}
main=():>int64=>{
    let nodes:array<Node>=[Node[[7] 41]]
    return walk(@nodes)
}'''
CASES=[(ROOT/'tests/fixtures/element_getter_appends.dewy').read_text()]
# Replacing or removing the element must leave the earlier read intact.
CASES.append(HEADER+'change=(@nodes:array<Node>):>void=>{if nodes.length >? 0 {nodes[0]=Node[[9] 9]}}\n'+WALK)
CASES.append(HEADER+'change=(@nodes:array<Node>):>void=>{if nodes.length >? 0 {nodes.pop;}}\n'+WALK)
CASES.append(HEADER+'change=(@nodes:array<Node>):>void=>{nodes=[]}\n'+WALK)
CASES.append(HEADER+'change=(@nodes:array<Node>):>void=>{if nodes.length >? 0 {nodes[0].items.push(5)}}\n'+WALK)

@pytest.mark.parametrize('source', CASES)
def test_element_getter_appends(tmp_path, source):
    execute(tmp_path, 'element-getter', codegen(SrcFile(None, source), debug_locations=False))

def test_native_element_getter_appends(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
