"""An isolated later calculation cannot overwrite an earlier place projection.

`tick` also writes an array global: a scalar global has no storage that
could alias the projection, so writing only one would need no isolation.
`main` ticks once first: native code gives the static empty array owned
storage on its first `clear`.
"""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = '''$explicit_copies
let ticks:int64=0
let log:array<int64>=[]
tick=():>void=>{ticks+=1 log.clear()}
Box:type=[items:array<int64>]
index=(items:array<int64>):>int64=>{
    let cursor:int64=0
    if items.length>?1 {cursor=1}
    return cursor
}
read=(items:array<int64> at:int64):>int64=>if at>=?0 and at<?items.length items[at] else 1
forward=(@box:Box):>int64=>{
    tick()
    return read(box.items index(box.items))
}
main=():>int64=>{
    let box=Box[[20 42]]
    tick()
    let before:int64=_arena_allocated_bytes
    loop i in [0..1000) {if forward(@box) not=?42 return 1}
    return if _arena_allocated_bytes=?before and ticks=?1001 42 else 2
}
'''
CASES = [SOURCE,
    SOURCE.replace('read=(items:', 'next=(items:array<int64>):>int64=>index(items)\nread=(items:')
          .replace('read(box.items index(box.items))', 'read(box.items next(box.items))'),
]
ERRORS = [SOURCE.replace('index(box.items)', 'index(@box.items)')
                .replace('index=(items:', 'index=(@items:')
                .replace('let cursor:int64=0', 'items.clear()\n    let cursor:int64=0'),
    SOURCE.replace('let cursor:int64=0', 'tick()\n    let cursor:int64=0'),
    SOURCE.replace('let cursor:int64=0', 'let address=items transmute int64\n    let cursor:int64=0'),
]


@pytest.mark.parametrize('source', CASES)
def test_nested_place_argument_loan(tmp_path, source):
    execute(tmp_path, 'nested-place-loan', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_later_argument_still_requires_independence(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_nested_place_argument_requires_isolation(monkeypatch):
    from dewy.backend.udewy import borrowing
    monkeypatch.setattr(borrowing, 'isolated_functions', lambda *args: set())
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, SOURCE), debug_locations=False)


def test_native_nested_place_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
