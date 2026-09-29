"""Last-use array records transfer only after proving element independence."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/inline_record_element_moves.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('let items=make()', 'const items=make()'),
    SOURCE.replace('Inner:type=', 'Inner = type of '),
    SOURCE.replace('Inner:type=[values:array<int64>]', 'Inner:type=[values:array<int64> label:string="label" flag:int64?=42]'),
    SOURCE.replace('let first=items[0]', 'let index:int64=0\n    let first=items[index]'),
    SOURCE.replace('$explicit_copies', '').replace('let before:int64=_arena_allocated_bytes',
        'let saved=items.copy()\n    let before:int64=_arena_allocated_bytes').replace(
        'if _arena_allocated_bytes-before >?1024 return 2',
        'if saved[0].values.length not=?1024 or saved[0].values[1023] not=?1023 return 2'),
]
RETURNED = SOURCE.replace('work=():>int64=>{',
    'take=():>Inner=>{let items=make() $runtime_assert items.length>?0 return items[0]}\nwork=():>int64=>{')
RETURNED = RETURNED.replace('    let items=make()\n    $runtime_assert items.length =? 2\n    let before:int64=_arena_allocated_bytes\n    let first=items[0]',
    '    let first=take()\n    let before:int64=_arena_allocated_bytes').replace(
    '    if items[1].values.length not=?1 or items[1].values[0] not=?42 return 1\n', '')
CASES.append(RETURNED)
DYNAMIC = SOURCE.replace('work=():>int64=>{', 'work=(index:int64):>int64=>{').replace(
    '    let first=items[0]', '    $runtime_assert 0<=?index<?items.length\n    let first=items[index]').replace(
    '    if items[1].values.length not=?1 or items[1].values[0] not=?42 return 1\n', '').replace('work()', 'work(0)')
# The compound assertion's diagnostic reserves a reusable scratch-region
# header on the hosted route. Warm that pool before measuring retained bytes.
DYNAMIC = DYNAMIC.replace('main=():>int64=>{', 'main=():>int64=>{\n    if work(0) not=?42 return 6')
CASES.append(DYNAMIC)
ERRORS = [SOURCE.replace('first.values.push(42)', 'first.values.push(42)\n    if items[0].values.length=?0 return 6'),
    SOURCE.replace('let first=items[0]', 'const alias=@items[0]\n    let first=items[0]').replace(
        'if items[1]', 'if alias.values.length=?0 return 6\n    if items[1]'),
    SOURCE.replace('let first=items[0]', 'let first=items[0]\n    let again=items[0]').replace(
        'if items[1]', 'if again.values.length=?0 return 6\n    if items[1]'),
]

@pytest.mark.parametrize('source', CASES)
def test_record_element_moves(tmp_path, source):
    execute(tmp_path, 'record-element-move', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_record_element_live_read_rejects(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_record_element_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_record_element_copy_positive_control(tmp_path, monkeypatch):
    from dewy.backend.udewy.lower import _Lowerer
    from dewy.semantic import hir
    compute = _Lowerer._compute_moves
    def without_elements(self, literal):
        elements = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.Index)}
        return compute(self, literal) - elements
    monkeypatch.setattr(_Lowerer, '_compute_moves', without_elements)
    execute(tmp_path, 'record-element-copy-control',
            codegen(SrcFile(None, SOURCE.replace('$explicit_copies', '')), debug_locations=False), expected=4)
