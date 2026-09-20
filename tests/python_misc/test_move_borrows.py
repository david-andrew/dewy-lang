"""A live inferred view extends its owner's storage liveness across moves."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_move_preserves_live_borrow_snapshots(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/move_live_borrows.dewy')
    execute(tmp_path, 'move-live-borrows', codegen(source, debug_locations=False))


def test_live_record_view_prevents_array_field_transfer(tmp_path):
    from dewy.backend.udewy import lower
    source = SrcFile(None, '''
Box:type=[value:int64]
Holder:type=[items:array<Box>]
make=():>array<Box>=>[Box[42]]
main=():>int64=>{
    let source=make()
    if source.length <? 1 return 1
    let snapshot=source[0]
    let taken=Holder[source]
    if taken.items.length <? 1 return 2
    taken.items[0].value=99
    return snapshot.value
}
''')
    code = codegen(source, debug_locations=False)
    assert any(not note.moved and '`source` is copied when stored in a field' in note.message
               for note in lower.last_move_notes)
    execute(tmp_path, 'move-live-field-borrow', code)
