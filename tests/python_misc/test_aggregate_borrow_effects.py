"""Allocation contracts and lowering agree on ordinary aggregate forwarding."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/aggregate_borrow_effects.dewy'
ERRORS = [
    'Box:type=[text:string]\n'
    'read=(text:string n:int64):>int64=>text.length+n\n'
    'change=(@box:Box):>int64=>{box.text="changed" return 0}\n'
    'forward=(box:Box):>int64 & no allocates=>read(box.text change(@box))',

    'Box:type=[value:int64]\n'
    'change=(box:Box):>int64=>{box.value=1 return box.value}\n'
    'forward=(box:Box):>int64 & no allocates=>change(box)',
    'Box:type=[value:int64]\n'
    'forward=(box:Box f:(b:Box):>int64 & no_effects):>int64 & no allocates=>f(box)',
    'copy=(text:string):>string=>text.copy()\n'
    'forward=(text:string):>string & no allocates=>copy(text)',
    'Token=type of [value:int64 $__drop__ release=():>void=>{}]\n'
    'consume=(item:Token):>int64=>item.value\n'
    'forward=(item:Token):>int64 & no allocates=>consume(item)',
]


def test_aggregate_forwarding_needs_no_allocation(tmp_path):
    execute(tmp_path, 'aggregate-borrows', codegen(SrcFile.from_path(FIXTURE), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_unproven_aggregate_forwarding_requires_allocation(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_aggregate_borrow_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[FIXTURE.read_text()], errors=ERRORS)
