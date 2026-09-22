"""Projected parent storage must adopt the tags of its narrowed child union."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

FAMILY='''Token=$abstract type of [loc:int64]
Left=type of Token & [value:int64]
Right=type of Token & [padding:int64 value:int64]
Other=type of Token & []
'''
CASES=[FAMILY+body for body in [
'''read=(items:array<Token>):>int64=>{if items.length=?0 return 0
if items[0] is? Left|Right {let saved=items[0] return saved.value}
return 0}
main=():>int64=>read([Left[0 20]])+read([Right[0 999 22]])''',
'''read=(items:array<Token|none>):>int64=>{if items.length=?0 return 0
if items[0] is? Left|Right {let saved=items[0] return saved.value}
return 0}
main=():>int64=>read([Left[0 20]])+read([Right[0 999 22]])''',
'''Box:type=[node:Token|none]
read=(box:Box):>int64=>{if box.node is? Left|Right {let saved=box.node return saved.value} return 0}
main=():>int64=>read(Box[Left[0 20]])+read(Box[Right[0 999 22]])''',
'''read=(items:totaldict<"a" (Token|none)>):>int64=>{
if items["a"] is? Left|Right {let saved=items["a"] return saved.value} return 0}
main=():>int64=>read(["a"->Left[0 20]])+read(["a"->Right[0 999 22]])''',
]]

CASES += [FAMILY+body for body in [
'''read=(items:totaldict<"a" Token>):>int64=>{
if items["a"] is? Left|Right {const saved=items["a"] return saved.value} return 0}
main=():>int64=>read(["a"->Left[0 20]])+read(["a"->Right[0 999 22]])''',
'''take=(items:array<Token|none>):>Left|none=>{
if items.length=?0 return none
if items[0] is? Left|none return items[0] return none}
main=():>int64=>{let items:array<Token|none>=[Left[0 42]]
let saved=take(items) items.clear()
if saved isnt? none return saved.value return 1}''',
]]

CASES += [FAMILY+body for body in [
'''Box:type=[node:Token read=():>int64=>{if node is? Left|Right {let saved=node return saved.value} return 0}]
main=():>int64=>Box[Left[0 20]].read()+Box[Right[0 999 22]].read()''',
'''Box:type=[node:Token|none read=():>int64=>{if node is? Left|Right {let saved=node return saved.value} return 0}]
main=():>int64=>Box[Left[0 20]].read()+Box[Right[0 999 22]].read()''',
]]

@pytest.mark.parametrize('source',CASES)
def test_projected_family_union(source,tmp_path):
    execute(tmp_path,'projected-family',codegen(SrcFile(None,source)))

def test_native_projected_family_unions(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=[])
