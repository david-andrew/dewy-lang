"""A conditional value inherits its enclosing ownership-transfer position."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ARRAY = '''$explicit_copies
pick=(flag:bool):>array<int64>=>{
    let a:array<int64>=[42]
    let b:array<int64>=[42]
    return if flag a else b
}
main=():>int64=>{
    # Warm allocator bookkeeping before measuring retained value storage.
    {let warm=pick(true) let other=pick(false)}
    let before=_arena_live_bytes
    loop repeat in 0..49 {
        let a=pick(true)
        let b=pick(false)
        if a.length not=?1 or b.length not=?1 return 1
        if a[0] not=?42 or b[0] not=?42 return 2
    }
    return if _arena_live_bytes=?before 42 else 3
}
'''
RECORD = '''$explicit_copies
Box:type=[items:array<int64>]
pick=(flag:bool):>Box=>{
    let a=Box[[42]] let b=Box[[42]]
    return if flag a else b
}
main=():>int64=>{
    let a=pick(true) let b=pick(false)
    return if a.items.length=?1 and b.items.length=?1 a.items[0] else 0
}
'''
CASES = [ARRAY, RECORD,
    ARRAY.replace('return if flag a else b', 'return if flag {let ignored=7 a} else {let ignored=9 b}'),
    ARRAY.replace('return if flag a else b', 'loop repeat in 0..2 {return if flag a else b}\nreturn a'),
    ARRAY.replace('return if flag a else b', 'return if flag a else {a.push(1) b}'),
    ARRAY.replace('return if flag a else b', 'return if flag a else if not flag b else a'),
    ARRAY.replace('return if flag a else b', 'let selected=if flag a else b\nreturn selected'),
    ARRAY.replace('return if flag a else b', 'loop repeat in 0..2 {let selected=if flag a else b selected.push(9) $runtime_assert selected.length=?2}\nreturn a').replace('$explicit_copies\n', ''),
]
ERROR_BASE = ARRAY.replace('    return if flag a else b', '    if flag a.push(1)\n    return if flag a else b')
ERRORS = [ERROR_BASE.replace('return if flag a else b', body) for body in [
    'let selected=if flag a else b\na.push(1)\nreturn selected',
    'const loan=@a\nlet selected=if flag a else b\n$runtime_assert loan.length=?1\nreturn selected',
    'loop repeat in 0..2 {let selected=if flag a else b selected.push(9) $runtime_assert selected.length=?2}\nreturn a',
]]


@pytest.mark.parametrize('source', CASES)
def test_conditional_value_move(tmp_path, source):
    execute(tmp_path, 'conditional-value-move', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_conditional_value_keeps_live_sources(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_conditional_value_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
