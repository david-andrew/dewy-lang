"""Unrelated raw effects do not force copies of proven unexposed arguments."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
SOURCE = (FIXTURES / 'unrelated_raw_array_borrows.dewy').read_text()
CASES = [SOURCE,
    # Local growth changes representation, not read-only call semantics.
    SOURCE.replace('let values=make()', 'let values:array<int64>=[]\n    loop i in [0..42) {values.push(i)}'),
    SOURCE.replace('return values.length', 'if values.length>?0 return values[0]+42\n    return 0'),
    '''let pointer:int64=0
read=(snapshot:array<int64>):>int64=>{
    __store_i64__(99 pointer)
    return if snapshot.length>?0 snapshot[0] else 0
}
main=():>int64=>{
    let values:array<int64>=[42]
    let descriptor=values transmute int64
    pointer=__load_i64__(descriptor)
    let answer=read(values)
    return if answer=?42 and values[0]=?99 42 else 1
}''',
    '''let pointer:int64=0
read=(snapshot:array<int64> address:int64):>int64=>{
    __store_i64__(99 address)
    return if snapshot.length>?0 snapshot[0] else 0
}
main=():>int64=>{
    let values:array<int64>=[42]
    let descriptor=values transmute int64
    let answer=read(values __load_i64__(descriptor))
    return if answer=?42 and values[0]=?99 42 else 1
}''',
    '''read=(values:array<int64>):>int64=>{
    __syscall0__(39);
    let copy=values.copy()
    copy.clear
    return values.length
}
main=():>int64=>{let values:array<int64>=[]
loop i in [0..42) {values.push(i)}
if read(values) not=?42 return 3
let before:int64=_arena_live_bytes
loop i in [0..20) {if read(values) not=?42 return 1}
return if values.length=?42 and _arena_live_bytes=?before 42 else 2}''',
    # Raw exposure isolates both preexisting value aliases and later arguments.
    """read=(values:array<int64> pointer:int64):>int64=>{
    __store_i64__(99 pointer)
    return if values.length>?0 values[0] else 0
}
main=():>int64=>{
    let values:array<int64>=[42]
    let alias=values
    let pointer=__load_i64__(values transmute int64)
    let answer=read(alias pointer)
    return if answer=?42 and values[0]=?99 and alias[0]=?42 42 else 1
}""",
    """let values:array<int64>=[42]
read=(snapshot:array<int64>):>int64=>{
    __syscall0__(39);
    values.clear
    return if snapshot.length>?0 snapshot[0] else 0
}
forward=(@source:array<int64>):>int64=>read(source)
main=():>int64=>{
    let answer=forward(@values)
    return if answer=?42 and values.length=?0 42 else 1
}""",
    """let values:array<int64>=[42]
change=():>int64=>{values.clear return 0}
read=(snapshot:array<int64> ignored:int64):>int64=>{
    return if snapshot.length>?0 snapshot[0] else 0
}
forward=(@source:array<int64>):>int64=>read(source change())
main=():>int64=>{
    let answer=forward(@values)
    return if answer=?42 and values.length=?0 42 else 1
}""",

]

@pytest.mark.parametrize('source', CASES)
def test_unrelated_raw_call_borrows_array(tmp_path, source):
    execute(tmp_path, 'unrelated-raw-array', codegen(SrcFile(None, source)))


def test_native_unrelated_raw_array_borrows(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
