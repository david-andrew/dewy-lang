"""Array descriptor slots follow the same last-use proof as record elements."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
make=():>array<array<int64>>=>{
    let values:array<int64>=[]
    values.reserve(1025)
    loop i in [0..1024) {values.push(i)}
    return [values [42]]
}
work=():>int64=>{
    let items=make()
    $runtime_assert items.length=?2
    let before:int64=_arena_allocated_bytes
    let first=items[0]
    first.push(42)
    if items[1].length not=?1 or items[1][0] not=?42 return 1
    if _arena_allocated_bytes-before >?1024 return 2
    return if first.length=?1025 and first[1024]=?42 42 else 3
}
main=():>int64=>{
    # Warm reusable diagnostic scratch headers before checking steady state.
    if work() not=?42 return 6
    let before:int64=_arena_live_bytes
    loop i in [0..20) {if work() not=?42 return 4}
    return if _arena_live_bytes=?before 42 else 5
}
'''
CASES = [SOURCE, SOURCE.replace('let items=make()', 'const items=make()'),
    SOURCE.replace('$explicit_copies', '').replace('let before:int64=_arena_allocated_bytes',
        'let saved=items.copy()\n    let before:int64=_arena_allocated_bytes').replace(
        'if _arena_allocated_bytes-before >?1024 return 2',
        'if saved[0].length not=?1024 or saved[0][1023] not=?1023 return 2'),
]
RETURNED = SOURCE.replace('work=():>int64=>{',
    'take=():>array<int64>=>{let items=make() $runtime_assert items.length>?0 return items[0]}\nwork=():>int64=>{').replace(
    '    let items=make()\n    $runtime_assert items.length=?2\n    let before:int64=_arena_allocated_bytes\n    let first=items[0]',
    '    let first=take()\n    let before:int64=_arena_allocated_bytes').replace(
    '    if items[1].length not=?1 or items[1][0] not=?42 return 1\n', '')
CASES.append(RETURNED)
RENEWED = SOURCE.replace('    first.push(42)',
    '    items[0]=[7]\n    first.push(42)\n    if items[0].length not=?1 or items[0][0] not=?7 return 7')
CASES.append(RENEWED)
# Mutate the first binding so it owns storage, then transfer that descriptor
# through another local and container. Read-only view promotion is separate.
CASES.append(SOURCE.replace('    first.push(42)',
    '    first.push(7)\n    first.pop;\n    let second=first\n    let outer:array<array<int64>>=[second]\n    $runtime_assert outer.length>?0\n    let selected=outer[0]\n    selected.push(42)').replace(
    'first.length=?1025 and first[1024]=?42', 'selected.length=?1025 and selected[1024]=?42'))
ERRORS = [SOURCE.replace('first.push(42)', 'first.push(42)\n    if items[0].length=?0 return 6'),
    SOURCE.replace('let first=items[0]', 'const alias=@items[0]\n    let first=items[0]').replace(
        'if items[1]', 'if alias.length=?0 return 6\n    if items[1]')]

@pytest.mark.parametrize('source', CASES)
def test_nested_array_element_transfers(tmp_path, source):
    execute(tmp_path, 'nested-array-element', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_nested_array_live_reader_rejects(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_nested_array_element_transfers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_nested_array_copy_positive_control(tmp_path, monkeypatch):
    from dewy.backend.udewy.lower import _Lowerer
    from dewy.semantic import hir
    compute = _Lowerer._compute_moves
    def without_elements(self, literal):
        elements = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.Index)}
        return compute(self, literal) - elements
    monkeypatch.setattr(_Lowerer, '_compute_moves', without_elements)
    execute(tmp_path, 'nested-array-copy-control',
            codegen(SrcFile(None, SOURCE.replace('$explicit_copies', '')), debug_locations=False), expected=6)
