"""A last-use record field can leave an owned optional cell without copying."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/optional_record_field_moves.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('Box:type=[values:array<int64>]', 'Inner:type=[values:array<int64>]\nBox:type=[inner:Inner]')
          .replace('Box[values]', 'Box[Inner[values]]').replace('maybe.values', 'maybe.inner.values'),
    SOURCE.replace('Box?', 'Box|bool').replace('return none', 'return false').replace('maybe is? none', 'maybe is? bool'),
]
SHARED = '''Box:type=[values:array<int64>]
make=():>Box?=>{let values:array<int64>=[] values.push(20) return Box[values]}
main=():>int64=>{
 let before:int64=_arena_live_bytes
 let original=make()
 let copy=original
 if copy is? none return 1
 let values=copy.values
 values.push(22)
 if original is? none return 2
 if original.values.length not=?1 or original.values[0] not=?20 return 3
 return if values.length=?2 values[0]+values[1] else 4
}'''
SHARED = SHARED.replace('main=()', 'exercise=()').replace(' let before:int64=_arena_live_bytes\n', '')
SHARED += '\nmain=():>int64=>{let before:int64=_arena_live_bytes loop i in [0..100) {if exercise() not=?42 return 1} return if _arena_live_bytes=?before 42 else 2}'
CASES.append(SHARED)
CASES.append(SOURCE.split('work=')[0]+'''take=():>array<int64>=>{
 let maybe=make(true)
 if maybe is? none return []
 return maybe.values
}
main=():>int64=>{let values=take() values.push(22) return if values.length=?2 values[0]+values[1] else 1}
''')
ERRORS = [SOURCE.replace('let values=maybe.values', 'let values=maybe.values\nif maybe.values.length>?10 return 5'),
    SOURCE.replace('let values=maybe.values', 'const alias=@maybe\nlet values=maybe.values\nif alias.values.length>?10 return 5')]

@pytest.mark.parametrize('source', CASES)
def test_optional_record_field_moves(tmp_path, source):
    execute(tmp_path, 'optional-field-move', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_optional_field_move_keeps_owner_readers(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_optional_record_field_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_optional_field_allocation_positive_control(tmp_path, monkeypatch):
    from dewy.backend.udewy.lower import _Lowerer
    from dewy.semantic import hir
    compute = _Lowerer._compute_moves
    def without_fields(self, literal):
        fields = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.MemberAccess)}
        return compute(self, literal) - fields
    monkeypatch.setattr(_Lowerer, '_compute_moves', without_fields)
    execute(tmp_path, 'optional-field-copy-control',
            codegen(SrcFile(None, SOURCE.replace('$explicit_copies', '')), debug_locations=False), expected=3)
