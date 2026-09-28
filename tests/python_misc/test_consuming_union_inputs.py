"""Direct single-use union inputs own the payload they donate onward."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

BASE='''$explicit_copies
Box:type=[items:array<int64>]
Node:type=Box|none
append=(@output:array<Node> node:Node):>void=>{output.push(node)}
make=():>Node=>Box[[42]]
work=():>int64=>{
 let output:array<Node>=[]
 append(@output make())
 $runtime_assert output.length=?1
 let found=output[0]
 if found is? Box and found.items.length>?0 return found.items[0]
 return 1
}
main=():>int64=>{
 loop i in [0..1000) {if work() not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..1000) {if work() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}'''
CASES=[BASE,
 BASE.replace(' append(@output make())',' let local=make()\n append(@output local)'),
 BASE.replace(' append(@output make())',' append(node=make() output=@output)'),
 BASE.replace('make=','forward=(@output:array<Node> node:Node):>void=>append(@output node)\nmake=',1).replace(' append(@output make())',' forward(@output make())'),
 BASE.replace('Node:type=Box|none','Node:type=Box|string|none'),
 BASE.replace('append=(@output:array<Node> node:Node):>void=>{output.push(node)}',
              'append=(@output:array<Node> node:Node):>void=>{output.insert(node 0)}'),
 BASE.replace(' append(@output make())',' let local=make()\n append(@output local.copy())\n if local is? Box {local.items.clear()}'),
]
CASES.extend([
 BASE.replace('append(@output make())', 'append(@output Box[[42]])'),
 BASE.replace('Node:type=Box|none','Node:type=array<int64>|none')
     .replace('make=():>Node=>Box[[42]]','make=():>Node=>[42]')
     .replace('if found is? Box and found.items.length>?0 return found.items[0]',
              'if found isnt? none and found.length>?0 return found[0]'),
 BASE.replace('make=():>Node=>Box[[42]]','make=():>Node=>none')
     .replace('if found is? Box and found.items.length>?0 return found.items[0]',
              'if found is? none return 42'),
])
ERRORS=[BASE.replace(' append(@output make())',' let local=make()\n append(@output local)\n if local is? Box {local.items.clear()}'),
 BASE.replace('output.push(node)','output.push(node) output.push(node)'),
 BASE.replace('output.push(node)','if output.length=?0 {output.push(node)}')]

@pytest.mark.parametrize('source',CASES)
def test_consuming_union_input(tmp_path,source):
    execute(tmp_path,'consuming-union',codegen(SrcFile(None,source),debug_locations=False))

@pytest.mark.parametrize('source',ERRORS)
def test_consuming_union_requires_single_transfer(source):
    with pytest.raises(ReportException,match='unproven copy'):
        codegen(SrcFile(None,source),debug_locations=False)

def test_native_consuming_union_inputs(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
