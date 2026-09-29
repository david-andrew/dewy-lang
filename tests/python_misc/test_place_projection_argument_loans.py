"""A sole place formal can lend an unwritten sibling projection."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
Box:type=[items:array<int64> counter:int64]
Pair:type=[items:array<int64> offset:int64]
read=(pair:Pair):>int64 & no_effects=>pair.items.length+pair.offset
forward=(@box:Box):>int64 & reads<box> & mutates<box.counter> & no allocates=>{
    box.counter+=1
    return read(Pair[box.items 40])
}
work=(@box:Box):>int64=>{
    let before:int64=_arena_allocated_bytes
    loop i in 0.. and i<?1000 {if forward(@box) not=?42 return 1}
    return if box.counter=?1000 and _arena_allocated_bytes=?before 42 else 2
}
main=():>int64=>{let box=Box[[20 22] 0] return work(@box)}
'''
CASES = [SOURCE, SOURCE.replace('return read(Pair[box.items 40])',
    'const items=box.items\n    return read(Pair[items 40])')]
ERRORS = [SOURCE.replace('box.counter+=1', 'box.items.clear'),
    SOURCE.replace('read=(pair:Pair)', 'read=(pair:Pair unused:int64)')
        .replace('forward=', 'change=(@box:Box):>int64=>{box.items.clear return 0}\nforward=')
        .replace('read(Pair[box.items 40])', 'read(Pair[box.items 40] change(@box))'),
    # The second place could be the first at a call. A write through it must
    # not leave the first parameter's storage marked as stable.
    SOURCE.replace('forward=(@box:Box)', 'forward=(@box:Box @other:Box)')
        .replace('& mutates<box.counter>', '& mutates<box.counter> & mutates<other>')
        .replace('read=(pair:Pair)', 'read=(pair:Pair unused:int64)')
        .replace('forward=', 'change=(@box:Box):>int64=>{box.items.clear return 0}\nforward=')
        .replace('read(Pair[box.items 40])', 'read(Pair[box.items 40] change(@other))')
        .replace('let before:int64=', 'let other=Box[[1] 0]\n    let before:int64=')
        .replace('forward(@box)', 'forward(@box @other)'),
]

@pytest.mark.parametrize('source', CASES)
def test_place_projection_argument_loans(tmp_path, source):
    execute(tmp_path, 'place-projection-loan', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_place_projection_requires_no_overlapping_write(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_place_projection_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
