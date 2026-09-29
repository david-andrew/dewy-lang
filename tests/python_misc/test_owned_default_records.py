"""Direct owning record parameters retain lazy defaults and exact cleanup."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute
from test_disjoint_field_arguments import START, TAKE, WORK

FACTORY = START.replace('make=(size:int64):>Box', 'make_inner=(size:int64):>Inner').replace('return Box[Inner[values]]', 'return Inner[values]') + 'make=(size:int64):>Box=>Box[make_inner(size)]\n'
SOURCE = (FACTORY + '''let defaults:int64=0
default_inner=():>Inner=>{defaults+=1 return make_inner(1024)}
''' + TAKE.replace('inner:Inner answer:int64', 'inner:Inner=default_inner() answer:int64=42') + WORK)
SOURCE = SOURCE.replace('return result\n}', '''if defaults not=?0 return 5
 if take() not=?42 or defaults not=?1 return 6
 if take(answer=42) not=?42 or defaults not=?2 return 7
 defaults=0
 return result
}''')
CASES = [SOURCE,
    SOURCE.replace('take(box.inner box.answer)', 'take(answer=box.answer inner=box.inner)'),
    SOURCE.replace('Inner:type=[values:array<int64>]', 'Inner:type=[values:array<int64> label:string="preserved"]'),
]
# A first-class function retains its ordinary borrowed calling convention.
CALLBACK = '''Box:type=[values:array<int64>]
default_box=():>Box=>Box[[20]]
take=(box:Box=default_box()):>int64=>{box.values.push(22) return if box.values.length=?2 box.values[0]+box.values[1] else 1}
work=():>int64=>{let box=default_box() const callback=@take if callback(box) not=?42 return 2 return if box.values.length=?1 take() else 3}
main=():>int64=>{let before:int64=_arena_live_bytes loop i in [0..20) {if work() not=?42 return 4} return if _arena_live_bytes=?before 42 else 5}
'''
CASES.append(CALLBACK)
ERRORS = [SOURCE.replace('let result=take(box.inner box.answer)', 'let result=take(box.inner box.answer)\n if box.inner.values.length=?0 return 8')]

@pytest.mark.parametrize('source', CASES)
def test_owned_default_record(tmp_path, source):
    execute(tmp_path, 'owned-default-record', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_owned_default_preserves_later_reads(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_owned_default_records(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
