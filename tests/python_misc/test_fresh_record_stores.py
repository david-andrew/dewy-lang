"""An explicit record copy is already an owner when stored in a container."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

PREFIX='''$explicit_copies
Row:type=const [values:array<int64>]
Box:type=const [row:Row?]
work=(box:Box):>int64=>{
'''
SUFFIX='''
 if saved.row is? none or saved.row.values.length<?1 return 1
 return saved.row.values[0]
}
main=():>int64=>work(Box[Row[[42]]])'''
CASES=[PREFIX+body+SUFFIX for body in [
 'let boxes:array<Box>=[]\n boxes.push(box.copy())\n if boxes.length<?1 return 2\n let saved=boxes[0].copy()',
 'let boxes:array<Box>=[box.copy()]\n let saved=boxes[0].copy()',
 "let boxes:dict<string Box>=[]\n boxes['key']=box.copy()\n let saved=boxes['key'].copy()",
 'let boxes:array<Box>=[Box[none]]\n boxes[0]=box.copy()\n let saved=boxes[0].copy()',
]]

@pytest.mark.parametrize('source',CASES)
def test_fresh_record_store(tmp_path,source):
 execute(tmp_path,'fresh-store',codegen(SrcFile(None,source),debug_locations=False))


def test_native_fresh_record_stores(tmp_path):
 from test_bootstrap_structural_text import build_program_driver,check_structural_text
 check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=[])

CASES.append(CASES[2].replace('main=():>int64=>work(Box[Row[[42]]])', '''main=():>int64=>{
 loop i in [0..100) {if work(Box[Row[[42]]]) not=?42 return 2}
 let before:int64=_arena_live_bytes
 loop i in [0..100) {if work(Box[Row[[42]]]) not=?42 return 3}
 return if _arena_live_bytes=?before 42 else 4
}'''))
