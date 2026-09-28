"""Stable local owners can lend narrowed union fields at call boundaries."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/scoped_union_argument_loans.dewy').read_text()
CASES = [SOURCE,
    SOURCE.replace('same(interval.lower interval.upper)', 'same(b=interval.upper a=interval.lower)'),
    SOURCE.replace('Bounds[42 42]', 'Bounds[0x100000000000000000000 0x100000000000000000000]'),
    SOURCE.replace('same(interval.lower interval.upper)', 'same(interval.lower as bigint? interval.upper)'),
    SOURCE.replace('return if same(interval.lower interval.upper) 42 else 3',
                   '''let before:int64=_arena_allocated_bytes
    loop i in 0.. and i<?1000 {if not same(interval.lower interval.upper) return 3}
    return if _arena_allocated_bytes=?before 42 else 4'''),
    # A local exact member can use the same call-only union wrapper.
    '''$explicit_copies
Box:type=[items:array<int64>]
make=():>Box=>Box[[20 22]]
read=(box:Box?):>int64=>if box is? none 0 else box.items.length+40
main=():>int64=>{let box=make() return read(box)}''',
]
ERRORS = [
    SOURCE.replace('return a=?b', 'a=7\n    return a=?b'),
    SOURCE.replace('same=(a:bigint? b:bigint?)', 'same=(a:bigint? b:bigint? ignored:int64)')
          .replace('main=', 'alter=(@value:Bounds?):>int64=>{if value is? none return 0 value.lower=7 return 0}\nmain=')
          .replace('same(interval.lower interval.upper)', 'same(interval.lower interval.upper alter(@interval))'),
]
# Without strict mode the conflicting later write must still produce a
# snapshot, so `same` observes the first field's value before the write.
CASES.append(ERRORS[1].replace('$explicit_copies\n', ''))

@pytest.mark.parametrize('source', CASES)
def test_scoped_union_argument_loan(tmp_path, source):
    execute(tmp_path, 'scoped-union-loan', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unproved_scoped_union_argument_keeps_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_scoped_union_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
