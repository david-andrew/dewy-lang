"""Insertion reports its value's allocator escape, independently of its index."""
import pytest
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

SOURCE = '''label=(n:int64):>string=>"item {n}"
main=():>int64=>{
    let arena=Arena[]
    let values:array<string>=[]
    $allocator(@arena) {values.insert(label(42) 0)}
    arena.reset()
    return if values.length=?1 and values[0]=?"item 42" 42 else 1
}'''
CASES = [SOURCE, SOURCE.replace('label(42) 0', 'value=label(42) idx=0'),
         '$explicit_copies\n'+SOURCE.replace('label(42) 0', 'label(42).copy() 0')]
ERRORS = ['$explicit_copies\n'+source for source in CASES[:2]]

@pytest.mark.parametrize('source', CASES)
def test_allocator_insert_escape(tmp_path, source):
    compiled=codegen(SrcFile(None, source), debug_locations=False)
    if not source.startswith('$explicit_copies'):
        notes=[note for note in lower.last_copy_notes if 'leave the `$allocator(@arena)` block' in note.message]
        assert len(notes)==1 and notes[0].site=='stored into `values`'
    execute(tmp_path, 'allocator-insert', compiled)

@pytest.mark.parametrize('source', ERRORS)
def test_allocator_insert_requires_explicit_escape_copy(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))

def test_native_allocator_insert_escapes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
