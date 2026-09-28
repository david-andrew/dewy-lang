"""Proven constant selectors share literal-slot ownership and keep evaluation."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

HEADER = '''let trace:int64=0
let selections:int64=0
let seen:int64=0
Token=type of [id:int64 $__drop__ release=():>void=>{trace=trace*10+id}]
consume=(value:Token):>int64=>value.id
choose=(value:int64):>0=>{selections+=1 seen=value return 0}
'''
NAMED = HEADER + '''work=(flag:bool):>int64=>{
    let items=[Token[1] Token[2]]
    const slot=0
    if flag {consume(items[slot]);}
    return items[1].id
}
main=():>int64=>{
    if work(true) not=?2 or trace not=?12 return 1
    trace=0
    return if work(false)=?2 and trace=?21 42 else 2
}'''
CALLED = HEADER + '''work=(flag:bool):>int64=>{
    let items=[Token[1] Token[2]]
    if flag {consume(items[choose(items[1].id)]);}
    return items[1].id
}
main=():>int64=>{
    if work(true) not=?2 or trace not=?12 or selections not=?1 or seen not=?2 return 1
    trace=0
    return if work(false)=?2 and trace=?21 and selections=?1 42 else 2
}'''
CASES = [NAMED,
    NAMED.replace('const slot=0', 'const base=0 const slot=base'),
    NAMED.replace('const slot=0', 'const slot=2-2'),
    CALLED,
    CALLED.replace('return items[1].id',
                   'items[choose(items[1].id)]=Token[3] return items[0].id').replace(
                       'not=?2 or trace not=?12 or selections not=?1',
                       'not=?3 or trace not=?123 or selections not=?2').replace(
                           'work(false)=?2 and trace=?21 and selections=?1',
                           'work(false)=?3 and trace=?123 and selections=?3'),
    HEADER + '''Pair:type=[first:Token second:Token]
work=(flag:bool):>int64=>{
    let items=[[Pair[Token[1] Token[2]]]]
    const slot=0
    if flag {consume(items[slot][slot].first);}
    return items[slot][slot].second.id
}
main=():>int64=>{
    if work(true) not=?2 or trace not=?12 return 1
    trace=0
    return if work(false)=?2 and trace=?21 42 else 2
}''',
]
LIFETIME = (Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_constant_slots.dewy').read_text()
ERRORS = [NAMED.replace('return items[1].id', 'return items[slot].id'),
    CALLED.replace('if flag {consume', 'consume(items[1]);\nif flag {consume'),
    HEADER + '''work=():>void=>{
    let items=[Token[1] Token[2]]
    consume(items[1]);
    items[choose(items[1].id)]=Token[3]
}''',
    HEADER + '''select=(@items:array<Token>):>0=>{items.clear return 0}
work=(flag:bool):>void=>{
    let items:array<Token>=[Token[1] Token[2]]
    if flag {consume(items[select(@items)]);}
}''']


@pytest.mark.parametrize('source', CASES)
def test_constant_slot_ownership(tmp_path, source):
    execute(tmp_path, 'constant-slot', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_constant_slot_still_checks_lifetimes(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_constant_slot_ownership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_native_constant_slot_repeated_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[LIFETIME], errors=[])
