"""Loop writes invalidate initializer facts through the entire storage route."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''Box:type=[items:array<int64>=[]]
main=():>int64=>{
    let box=Box[]
    loop i in [0..3) {box.items.push(14)}
    let original=box.items
    box.items=[]
    let total:int64=0
    loop item in original {total+=item}
    return total
}'''
CASES = [SOURCE,
    SOURCE.replace('loop i in [0..3)', 'let i:int64=0 loop i<?3').replace('box.items.push(14)', 'box.items.push(14) i+=1'),
    SOURCE.replace('main=()', 'Outer:type=[inner:Box]\nmain=()').replace('let box=Box[]', 'let box=Outer[Box[]]').replace('box.items', 'box.inner.items'),
    SOURCE.replace('let box=Box[]', 'let boxes=[Box[]]').replace('box.items', 'boxes[0].items'),
]
ERRORS = [
    '''Box:type=[items:array<int64>]
main=():>int64=>{let box=Box[[42]] loop i in [0..1) {box.items.clear} return box.items[0]}''',
    '''Box:type=[items:array<int64>]
main=():>int64=>{let box=Box[[42]] loop i in [0..1) {box.items=[]} return box.items[0]}''',
    '''Box:type=[items:array<int64>]
Outer:type=[inner:Box]
main=():>int64=>{let box=Outer[Box[[42]]] loop i in [0..1) {box.inner.items=[]} return box.inner.items[0]}''',
]

@pytest.mark.parametrize('source', CASES)
def test_loop_field_facts(tmp_path, source):
    execute(tmp_path, 'loop-field-facts', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_loop_field_facts_invalidate(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_loop_field_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
