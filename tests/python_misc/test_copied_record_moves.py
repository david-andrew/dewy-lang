"""An explicit snapshot owns its fields and can subsequently transfer them."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute


SOURCE = '''$explicit_copies
Box:type=[items:array<int64>]
take=(input:Box):>Box?=>{
    let copied=input.copy()
    copied.items.push(22)
    return copied
}
work=():>int64=>{
    let input=Box[[20]]
    let output=take(input)
    if output is? none return 1
    if input.items.length not=?1 return 2
    return if output.items.length=?2 output.items[0]+output.items[1] else 3
}
main=():>int64=>{
    if work() not=?42 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i<?1000 {if work() not=?42 return 2}
    return if _arena_live_bytes=?before 42 else 3
}
'''
CASES = [SOURCE,
    SOURCE.replace('return copied', 'let transferred=copied\n    return transferred'),
    SOURCE.replace('Box?', 'Box').replace('    if output is? none return 1\n', ''),
    SOURCE.replace('return copied', 'return copied.items').replace('):>Box?', '):>array<int64>')
          .replace('    if output is? none return 1\n', '').replace('output.items', 'output'),
]
REJECTED = SOURCE.replace('return copied',
    'let result:Box?=copied\n    copied.items.clear()\n    return result')


@pytest.mark.parametrize('source', CASES)
def test_copied_record_moves(tmp_path, source):
    execute(tmp_path, 'copied-record', codegen(SrcFile(None, source), debug_locations=False))


def test_copied_record_move_still_requires_last_use():
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, REJECTED), debug_locations=False)


def test_native_copied_record_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[REJECTED])
