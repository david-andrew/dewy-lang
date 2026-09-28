"""Entry properties lend stable storage only for the iterator's lifetime."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/stable_entry_iteration.dewy').read_text()
MUTATED_KEYS = '''main=():>int64=>{
    let table:dict<string int64>=['a'->20 'b'->22]
    let count:int64=0
    loop key in table.keys {table.clear count+=1}
    return if count=?2 42 else 1
}'''
MUTATED_VALUES = '''main=():>int64=>{
    let table:dict<string int64>=['a'->20 'b'->22]
    let total:int64=0
    loop value in table.values {table.clear total+=value}
    return total
}'''
ORDINARY = '''main=():>int64=>{
    let table:dict<string int64>=['a'->20 'b'->22]
    let values=table.values
    table.clear
    return if values.length=?2 values[0]+values[1] else 1
}'''
SELECTOR = '''const tables:array<dict<string int64>>=[['a'->20 'b'->22]]
let calls:int64=0
select=():>0=>{calls+=1 return 0}
main=():>int64=>{
    let total:int64=0
    loop value in tables[select()].values {total+=value}
    return if calls=?1 total else 1
}'''


@pytest.mark.parametrize('source', [FIXTURE, MUTATED_KEYS, MUTATED_VALUES, ORDINARY, SELECTOR])
def test_entry_iteration_storage(tmp_path, source):
    execute(tmp_path, 'entry-iteration', codegen(SrcFile(None, source), debug_locations=False))


def test_native_entry_iteration_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=[FIXTURE, MUTATED_KEYS, MUTATED_VALUES, ORDINARY, SELECTOR], errors=[])
