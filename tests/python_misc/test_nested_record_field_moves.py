"""Inline record transfer preserves sibling readers and nested ownership."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/nested_record_field_moves.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('Inner:type=[values:array<int64>]', 'Inner:type=[values:array<int64> label:string="label"]'),
    SOURCE.replace('Inner:type=[values:array<int64>]', 'Inner:type=[values:array<int64> flag:int64?=42]'),
    SOURCE.replace('Box:type=[inner:Inner answer:int64=42]', 'Box:type=[inner:Inner answer:int64=42]\nOuter:type=[box:Box]')
          .replace('let box=make(1024)', 'let outer=Outer[make(1024)]').replace('box.inner', 'outer.box.inner').replace('box.answer', 'outer.box.answer'),
]
DICT = '''$explicit_copies
Box:type=[items:dict<int64 int64> answer:int64=42]
make=():>Box=>{let items:dict<int64 int64>=[] loop i in [0..1024) {items[i]=i} return Box[items]}
work=():>int64=>{
 let box=make()
 let before:int64=_arena_allocated_bytes
 let items=box.items
 if 0 in? items {items.pop(0);}
 if box.answer not=?42 return 1
 if _arena_allocated_bytes-before >?1024 return 2
 return if items.get(42)=?42 42 else 3
}
main=():>int64=>{let before:int64=_arena_live_bytes loop i in [0..20) {if work() not=?42 return 4} return if _arena_live_bytes=?before 42 else 5}
'''
CASES.append(DICT)
# Mutation of the taken record cannot empty a retained COW snapshot.
CASES.append(SOURCE.replace('$explicit_copies', '')
    .replace('let before:int64=_arena_allocated_bytes', 'let saved=box.copy()\n    let before:int64=_arena_allocated_bytes')
    .replace('if _arena_allocated_bytes-before >?1024 return 2',
             'if saved.inner.values.length not=?1024 or saved.inner.values[1023] not=?1023 return 2'))
CASES.append(SOURCE.replace('Inner:type=', 'Inner = type of '))
CASES.append(SOURCE.replace('Inner:type=[values:array<int64>]', 'Inner:type=[values:array<int64> payload:array<int64>|bool=[7]]'))
CASES.append('$explicit_copies\nInner:type=[values:array<int64>]\nBox:type=[inner:Inner answer:int64=42]\nwork=():>int64=>{let box=Box[Inner[[20]]] let inner=box.inner inner.values.push(22) return if box.answer=?42 and inner.values.length=?2 inner.values[0]+inner.values[1] else 1}\nmain=():>int64=>{let before:int64=_arena_live_bytes loop i in [0..20) {if work() not=?42 return 2} return if _arena_live_bytes=?before 42 else 3}\n')

ERRORS = [SOURCE.replace('inner.values.push(42)', 'inner.values.push(42)\n    if box.inner.values.length=?0 return 6'),
    SOURCE.replace('let inner=box.inner', 'const alias=@box.inner\n    let inner=box.inner').replace('if box.answer', 'if alias.values.length=?0 return 6\n    if box.answer')]

@pytest.mark.parametrize('source', CASES)
def test_nested_record_field_moves(tmp_path, source):
    execute(tmp_path, 'nested-record-field-move', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_nested_record_field_live_reader_rejects(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_nested_record_field_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_nested_record_copy_positive_control(tmp_path, monkeypatch):
    from dewy.backend.udewy.lower import _Lowerer
    from dewy.semantic import hir
    compute = _Lowerer._compute_moves
    def without_fields(self, literal):
        fields = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.MemberAccess)}
        return compute(self, literal) - fields
    monkeypatch.setattr(_Lowerer, '_compute_moves', without_fields)
    execute(tmp_path, 'nested-record-copy-control', codegen(SrcFile(None, SOURCE.replace('$explicit_copies', '')), debug_locations=False), expected=4)
