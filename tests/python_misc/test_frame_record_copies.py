"""An explicit fixed-record copy may own independent frame storage."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

PREFIX='''Point=type of [x:int64 y:int64]
Box=type of [point:Point]
'''
CASES=[
    PREFIX+'''work=():>int64 & no_effects=>{
let source=Box[Point[40 2]] let saved=source.copy()
saved.point.x=1 return source.point.x+source.point.y}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    PREFIX+'''work=(source:Box):>int64 & no_effects=>{
let saved=source.copy() saved.point.x+=saved.point.y return saved.point.x}
main=():>int64=>{let source=Box[Point[40 2]] let before=_arena_allocated_bytes
let n=work(source) return if source.point.x=?40 and _arena_allocated_bytes=?before n else 1}''',
    PREFIX+'''work=():>int64 & no_effects=>{
let saved=Box[Point[40 2]].copy().copy() saved.point.x+=saved.point.y return saved.point.x}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    PREFIX+'''work=():>int64 & no_effects=>{
let point=Point[40 2] let saved=Box[point.copy()] saved.point.x=1 return point.x+point.y}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    PREFIX+'''work=():>int64 & no_effects=>{
let source=Box[Point[40 2]] let total:int64=0
loop i in 0.. and i<?100000 {let copy=source.copy() copy.point.x=1 total+=copy.point.x}
return if total=?100000 source.point.x+source.point.y else 1}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
]
ERRORS=[
    PREFIX+'work=(source:Box):>Box & no allocates=>source.copy()',
    'Box:type=[items:array<int64>] work=(source:Box):>int64 & no allocates=>{let saved=source.copy() return saved.items.length}',
]

@pytest.mark.parametrize('source', CASES)
def test_explicit_record_copy_can_use_frame_storage(source,tmp_path):
    execute(tmp_path,'frame-copy',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source', ERRORS)
def test_copy_escaping_or_dynamic_storage_keeps_allocation_obligation(source):
    with pytest.raises(ReportException,match='effect contract'):
        codegen(SrcFile(None,source))

def test_native_frame_record_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
