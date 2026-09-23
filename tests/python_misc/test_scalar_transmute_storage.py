"""Scalar bit reinterpretation preserves the containing value's read-only loan."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES=[
    '''read=(xs:array<int64 length>?0>):>int64 & no allocates=>{
let bits=xs[0] transmute uint64 return bits transmute int64}
main=():>int64=>{let xs=[42] let before=_arena_allocated_bytes
let result=read(xs) return if _arena_allocated_bytes=?before result else 1}''',
    '''Cell:type=[value:int64]
read=(xs:array<Cell length>?0>):>int64 & no allocates=>{
let bits=xs[0].value transmute uint64 return bits transmute int64}
main=():>int64=>{let xs=[Cell[42]] let before=_arena_allocated_bytes
let result=read(xs) return if _arena_allocated_bytes=?before result else 1}''',
]

ERRORS=[
    'raw=(xs:array<int64>):>int64 & no allocates=>xs transmute int64',
    'raw=(n:int64):>array<int64> & no allocates=>n transmute array<int64>',
    'let count:int64=0 next=():>int64=>{count+=1 return count} raw=():>uint64 & no_effects=>next() transmute uint64',
]
@pytest.mark.parametrize('source',ERRORS)
def test_scalar_transmute_keeps_effect_boundary(source):
    with pytest.raises(ReportException,match='effect contract'):
        codegen(SrcFile(None,source))

@pytest.mark.parametrize('source',CASES)
def test_scalar_bits_keep_readonly_storage(tmp_path,source):
    execute(tmp_path,'scalar-transmute',codegen(SrcFile(None,source)))

def test_native_scalar_transmute_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
