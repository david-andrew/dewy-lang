"""Explicit fixed scalar-array copies need no heap or COW detachment."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES=[
    '''main=():>int64 & no_effects=>{let xs:array<uint8 length=?2>=[40 2]
return (xs[0] as int64)+(xs[1] as int64)}''',
    '''work=():>int64 & no_effects=>{let source=[40 2] let saved=source.copy()
saved[0]=1 return source[0]+source[1]}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    '''work=():>int64 & no_effects=>{let saved=[40 2].copy().copy() saved[0]=saved[0]+saved[1] return saved[0]}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    '''work=():>int64 & no_effects=>{let source=[true false] let saved=source.copy()
saved[0]=false return if source[0] and not saved[0] 42 else 1}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    '''work=():>int64 & no_effects=>{let source:array<uint8 length=?2>=[40 2] let saved=source.copy()
saved[0]=1 return (source[0] as int64)+(source[1] as int64)}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
    '''work=():>int64 & no_effects=>{let source=[40 2] let total:int64=0
loop i in 0.. and i<?100000 {let saved=source.copy() saved[0]=1 total+=saved[0]}
return if total=?100000 source[0]+source[1] else 1}
main=():>int64=>{let before=_arena_allocated_bytes let n=work()
return if _arena_allocated_bytes=?before n else 1}''',
]
ERRORS=[
    'work=(xs:array<int64>):>int64 & no allocates=>{let copy=xs.copy() return copy.length}',
    'work=():>array<int64> & no allocates=>{let xs=[40 2] return xs.copy()}',
    'work=():>int64 & no allocates=>{let xs=[40 2] let copy=xs.copy() copy.push(1) return copy.length}',
]

@pytest.mark.parametrize('source',CASES)
def test_fixed_array_copy_uses_frame(source,tmp_path):
    execute(tmp_path,'array-frame-copy',codegen(SrcFile(None,source)))

@pytest.mark.parametrize('source',ERRORS)
def test_array_copy_requires_bounded_nonescaping_storage(source):
    with pytest.raises(ReportException,match='effect contract'):
        codegen(SrcFile(None,source))

def test_frame_storage_does_not_discharge_invalid_length():
    with pytest.raises(ReportException):
        codegen(SrcFile(None, 'main=():>int64 & no_effects=>{let xs:array<uint8 length=?3>=[40 2] return 42}'))


def test_native_frame_array_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver,check_structural_text
    check_structural_text(build_program_driver(tmp_path),tmp_path,cases=CASES,errors=ERRORS)
