"""Set algebra borrows inputs, retaining a snapshot across conflicting evaluation."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [f'''$explicit_copies
main=():>int64=>{{
 let a:set<int64>=set[1 2]
 let b:set<int64>=set[2 3]
 let result=a {op} b
 a.clear() b.clear()
 return if result.length=?{count} and {member} in? result 42 else 0
}}''' for op,count,member in [('|',3,1),('&',1,2),('-',1,1),('xor',2,3)]]
CONFLICT = '''let left:set<int64>=set[1 2]
change=():>set<int64>=>{left.clear() return set[2 3]}
main=():>int64=>{
 let result=left & change()
 return if result.length=?1 and 2 in? result and left.length=?0 42 else 0
}'''
CASES += [CONFLICT, '$explicit_copies\n'+CONFLICT.replace('left & change()', 'left.copy() & change()')]
CASES += ['''$explicit_copies
make=():>set<int64>=>set[1 2]
work=():>int64=>{
 let a=make() | set[3]
 let b=set[2] & make()
 return if a.length=?3 and b.length=?1 42 else 0
}
main=():>int64=>{
 loop i in [0..1000) {if work() not=?42 return 1}
 let before:int64=_arena_live_bytes
 loop i in [0..1000) {if work() not=?42 return 2}
 return if _arena_live_bytes=?before 42 else 3
}''']
CASES.append('$explicit_copies\nBox:type=[values:set<int64>]\nmake=():>Box=>Box[set[1 2]]\nwork=():>int64=>{\n let result=make().values & set[2 3]\n return if result.length=?1 and 2 in? result 42 else 0\n}\nmain=():>int64=>{\n loop i in [0..1000) {if work() not=?42 return 1}\n let before:int64=_arena_live_bytes\n loop i in [0..1000) {if work() not=?42 return 2}\n return if _arena_live_bytes=?before 42 else 3\n}')
CASES += [
    """$explicit_copies
work=(a:set<int64> b:set<int64>):>int64=>{
 let result=a & b
 return if result.length=?1 and 42 in? result 42 else 0
}
main=():>int64=>{let values=set[42] return work(values values)}""",
    """let left:set<int64>=set[1 2]
Box:type=[value:set<int64>]
change=():>Box=>{left.clear() return Box[set[2 3]]}
main=():>int64=>{
 let result=left & change().value
 return if result.length=?1 and 2 in? result 42 else 0
}""",
]
CASES.append((Path(__file__).resolve().parents[1] / 'fixtures/set_algebra_borrows.dewy').read_text())
ERRORS = ['$explicit_copies\n'+CONFLICT]

@pytest.mark.parametrize('source', CASES)
def test_set_algebra_borrows(tmp_path, source):
    execute(tmp_path, 'set-algebra', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_set_algebra_snapshot_is_reported(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_set_algebra_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
