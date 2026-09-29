"""A last-use tagged field transfers its payload without losing cell cleanup."""
import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Box:type=[item:array<int64>|bool]
make=(present:bool):>Box=>Box[if present [20 22] else false]
take=(present:bool):>array<int64>|bool=>{
    let owner=make(present)
    return owner.item
}
work=(present:bool):>int64=>{
    let value=take(present)
    if value is? bool return if not value 42 else 1
    return if value.length=?2 value[0]+value[1] else 2
}
main=():>int64=>{
    if work(true) not=?42 or work(false) not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in [0..1000) {if work(true) not=?42 or work(false) not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [SOURCE,
    SOURCE.replace(':>Box=>Box[', ':>Box|none=>Box[').replace('return owner.item', 'if owner is? none return false\n    return owner.item'),
    SOURCE.replace('return owner.item', 'if owner.item is? bool return false\n    return owner.item'),
    SOURCE.replace('return owner.item', 'let result=owner.item\n    owner.item=false\n    return result'),
    SOURCE.replace('Box:type=[item:', 'Inner:type=[item:').replace('make=(present:', 'Box:type=[nested:Inner]\nmake=(present:')
          .replace('=>Box[if present [20 22] else false]', '=>Box[Inner[if present [20 22] else false]]').replace('owner.item', 'owner.nested.item'),
]
RETAINED = SOURCE.replace('return owner.item', 'let result=owner.item\n    if owner.item is? bool return false\n    return result')
CASES += [RETAINED, SOURCE.replace('return owner.item', 'let result=owner.item\n    return result')]
ERRORS = []
CASES.append(SOURCE.replace('return owner.item', '''let kept=owner.copy()
    let result=owner.item
    owner.item=false
    if kept.item is? array<int64> and kept.item.length not=?2 return false
    return result'''))
RECORD = SOURCE.replace('Box:type=', 'Payload:type=[items:array<int64>]\nBox:type=')
RECORD = RECORD.replace('array<int64>|bool', 'Payload|bool').replace('if present [20 22]', 'if present Payload[[20 22]]')
RECORD = RECORD.replace('value.length', 'value.items.length').replace('value[0]+value[1]', 'value.items[0]+value.items[1]')
CASES += [RECORD, RECORD.replace('return owner.item', 'if owner.item is? bool return false\n    return owner.item')]


@pytest.mark.parametrize('source', CASES)
def test_union_field_transfer(tmp_path, source):
    emitted = codegen(SrcFile(None, source), debug_locations=False)
    assert any('record field is moved when stored in a union' in note.message for note in lower.last_move_notes)
    execute(tmp_path, 'union-field-transfer', emitted)


def test_union_field_transfer_requires_last_use_proof(monkeypatch):
    monkeypatch.setattr(lower._Lowerer, '_movable_cell_owner', lambda *args: False)
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, SOURCE), debug_locations=False)


def test_native_union_field_transfers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
