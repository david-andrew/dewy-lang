"""Sorting permutes owners; by-value key callbacks receive checked copies."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures/lifecycle_resource_sort.dewy'
SOURCE=FIXTURE.read_text()


CASES=[SOURCE,
    SOURCE.replace('items.sort(key=@key)', 'items.sort(reverse=true key=@key)').replace('items[0].id not=?1', 'items[0].id not=?3').replace('items[2].id not=?3', 'items[2].id not=?1').replace('items[0].payload[0] not=?10', 'items[0].payload[0] not=?30'),
]
STRESS=SOURCE[:SOURCE.index('exercise=')]+'''exercise=():>int64=>{
    let items:array<Handle>=[]
    loop i in [1..41) {items.push(Handle[41-i [i]])}
    items.sort(key=@key)
    if items.length not=?40 return 1
    loop i in [0..items.length) {
        if items[i].id not=?i+1 return 2
        const payload=items[i].payload
        if payload.length not=?1 or payload[0] not=?40-i return 3
    }
    return 42
}
main=():>int64=>{
    let before:int64=_arena_live_bytes
    if exercise() not=?42 return 4
    return if copies=?40 and calls=?40 and drops=?80 and _arena_live_bytes=?before 42 else 5
}
'''
CASES.append(STRESS)

ERRORS=[
    SOURCE.replace('    $__copy__\n    duplicate=():>Handle=>{copies+=1 return Handle[id payload.copy()]}\n',''),
    '$explicit_copies\n'+SOURCE,
    """let copies:int64=0
Handle=type of [id:int64
    $__copy__
    duplicate=():>Handle=>{copies+=1 return Handle[id]}
    $__drop__
    release=():>void=>{}
]
key=(value:Handle):>int64=>value.id
reorder=():>void & allocates=>{let items=[Handle[2] Handle[1]] items.sort(key=@key)}
main=():>int64=>42
""",
    """let ambient:array<int64>=[1]
Handle=type of [id:int64
    $__copy__
    duplicate=():>Handle=>{ambient.clear return Handle[id]}
    $__drop__
    release=():>void=>{}
]
key=(value:Handle):>int64 & no_effects=>value.id
reorder=(@items:array<Handle>):>void=>items.sort(key=@key)
main=():>int64=>42
"""
]

@pytest.mark.parametrize('source', ERRORS)
def test_resource_sort_checks_copies_and_their_effects(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))



@pytest.mark.parametrize('source', CASES)
def test_resource_sort_owns_key_arguments(tmp_path, source):
    execute(tmp_path, 'resource-sort', codegen(SrcFile(None, source)))


def test_native_resource_sort(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
