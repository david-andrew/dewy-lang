"""A last-use record transfer must preserve values and element cleanup."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/record_element_moves.dewy').read_text()
HEADER = '''Record:type=[items:array<int64>]
read=(r:Record):>int64=>if r.items.length>?0 r.items[0] else 0
'''
PUSH = HEADER + '''main=():>int64=>{
    let value=Record[[42]]
    let values:array<Record>=[]
    values.push(value)
    return if values.length>?0 read(values[0]) else 1
}'''
TRANSFERS = [PUSH,
    PUSH.replace('let values:array<Record>=[]\n    values.push(value)', 'let values:array<Record>=[value]'),
    PUSH.replace('let values:array<Record>=[]\n    values.push(value)', 'let values:array<Record>=[Record[[1]]]\n    if values.length>?0 {values[0]=value}'),
    PUSH.replace('values.push(value)', 'values.insert(value 0)'),
]
PRESERVE = HEADER + '''main=():>int64=>{
    let value=Record[[42]]
    const held=value
    let values:array<Record>=[value]
    if values.length>?0 {values[0].items.clear}
    return read(held)
}'''
REPEATED = HEADER + '''main=():>int64=>{
    let value=Record[[42]]
    let values:array<Record>=[]
    loop i in [0..2) {values.push(value)}
    if values.length>=?2 {values[0].items.clear return read(values[1])}
    return 1
}'''
SHARED = PUSH.replace('let values:array<Record>=[]', 'let snapshot=value.copy()\n    let values:array<Record>=[]').replace(
    'return if values.length>?0 read(values[0]) else 1',
    'if values.length>?0 {values[0].items.clear}\n    return read(snapshot)')
FIXED = PUSH.replace('items:array<int64>', 'items:array<int64 length=1>')


@pytest.mark.parametrize('source', TRANSFERS)
def test_record_fields_move_into_elements(tmp_path, source):
    text = codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)
    assert any(note.moved and 'owned fields change owner' in note.message for note in lower.last_move_notes)
    execute(tmp_path, 'record-element', text)


@pytest.mark.parametrize('source', [SOURCE, PRESERVE, REPEATED, SHARED, FIXED])
def test_record_element_values_and_cleanup(tmp_path, source):
    execute(tmp_path, 'record-element-lifetimes', codegen(SrcFile(None, source), debug_locations=False))


def test_native_record_element_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=['$explicit_copies\n' + source for source in TRANSFERS]
        + [SOURCE, PRESERVE, REPEATED, SHARED, FIXED], errors=[])
