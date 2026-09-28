"""Owned tagged locals transfer payloads; views and explicit copies do not."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

HEADER = '''Box:type=[items:array<int64>]
value_of=(value:Box|none):>int64=>{
    if value is? Box and value.items.length>?0 return value.items[0]
    return 0
}
'''
RETURN = HEADER + '''make=(flag:bool):>Box|none=>{
    let value:Box|none=Box[[42]]
    if flag return value
    return none
}
main=():>int64=>value_of(make(true))+value_of(make(false))
'''
STORE = HEADER + '''main=():>int64=>{
    let value:Box|none=Box[[42]]
    let values:array<Box|none>=[]
    values.push(value)
    if values.length>?0 return value_of(values[0])
    return 1
}'''
CASES = [RETURN, STORE,
    STORE.replace('let values:array<Box|none>=[]\n    values.push(value)',
                  'let values:array<Box|none>=[value]'),
    HEADER + '''main=():>int64=>{
    let value:Box|none=Box[[42]]
    let taken:Box|none=value
    return value_of(taken)
}''',
    HEADER + '''Holder:type=[value:Box|none]
main=():>int64=>{
    let value:Box|none=Box[[42]]
    let taken=Holder[value]
    return value_of(taken.value)
}''',
]
# A retained snapshot must remain independent even if the original's direct
# spelling has no later reads. Its derived view extends the source lifetime.
PRESERVE = HEADER + '''main=():>int64=>{
    let value:Box|none=Box[[42]]
    const snapshot=value
    let values:array<Box|none>=[value]
    if values.length>?0 and values[0] is? Box {values[0].items.clear}
    return value_of(snapshot)
}'''
COPY = HEADER + '''main=():>int64=>{
    let value:Box|none=Box[[42]]
    let snapshot=value.copy()
    if value is? Box {value.items.clear}
    return value_of(snapshot)
}'''
REPEATED = HEADER + '''main=():>int64=>{
    let value:Box|none=Box[[42]]
    let values:array<Box|none>=[]
    loop i in [0..2) {values.push(value)}
    if values.length>=?2 and values[0] is? Box {values[0].items.clear}
    if values.length>=?2 and value_of(values[1])=?42 return value_of(value)
    return 1
}'''
GENERAL = RETURN.replace('Box|none', 'Box|int64|none')
FRAME = RETURN.replace('items:array<int64>', 'items:array<int64 length=1>')
NARROWED_ARRAY = '''Box:type=[items:array<int64>]
make=(flag:bool):>array<int64>|none=>if flag [42] else none
main=():>int64=>{
    let value=make(true)
    if value is? none return 1
    let box=Box[value]
    return if box.items.length>?0 box.items[0] else 2
}'''
NARROWED_RETURN = '''make=(flag:bool):>array<int64>|none=>if flag [42] else none
take=():>array<int64>=>{
    let value=make(true)
    if value is? none return []
    return value
}
main=():>int64=>{let values=take() return if values.length>?0 values[0] else 1}
'''
FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/union_local_moves.dewy'


@pytest.mark.parametrize('source', [*CASES, GENERAL])
def test_owned_union_local_moves(tmp_path, source):
    code = codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)
    assert any(note.moved and 'payload changes owner' in note.message for note in lower.last_move_notes)
    execute(tmp_path, 'union-move', code)


@pytest.mark.parametrize('source', [PRESERVE, COPY, REPEATED, FRAME, NARROWED_ARRAY, NARROWED_RETURN, FIXTURE.read_text()])
def test_union_moves_preserve_values_and_release(tmp_path, source):
    execute(tmp_path, 'union-move-lifetime', codegen(SrcFile(None, source), debug_locations=False))


def test_native_union_local_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=['$explicit_copies\n' + source for source in [*CASES, GENERAL]]
                          + [PRESERVE, COPY, REPEATED, FRAME, NARROWED_ARRAY, NARROWED_RETURN, FIXTURE.read_text()], errors=[])
