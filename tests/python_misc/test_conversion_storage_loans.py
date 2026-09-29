"""Typed value conversions do not expose unrelated owners to ambient writes."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_place_projection_argument_loans import SOURCE as PROJECTION_SOURCE
from test_scalar_projection import execute

SOURCE = (PROJECTION_SOURCE
    # Converting Unicode scalars does allocate its result. Check reclamation,
    # while strict policy rejects any incidental snapshot of box.items.
    .replace('_arena_allocated_bytes', '_arena_live_bytes')
    # Initialize the reusable conversion region before measuring live bytes.
    .replace('let before:int64=', "if units('ab') not=?2 return 3\n    let before:int64=")
    .replace(' & reads<box> & mutates<box.counter> & no allocates', '')
    .replace('forward=', "units=(text:string):>int64=>{let bytes=text as array<uint8> return bytes.length}\nforward=")
    .replace('Pair[box.items 40]', "Pair[box.items 38+units('ab')]"))
CASES = [SOURCE,
    SOURCE.replace('array<uint8>', 'array<uint32>'),
    SOURCE.replace('return bytes.length',
                   'if bytes.length>?0 {bytes[0]=90}\n return if text=?\'ab\' bytes.length else 0'),
]
ERRORS = [SOURCE.replace('box.counter+=1', 'box.counter+=1\n let address=box.items transmute int64'),
    SOURCE.replace('return read(Pair[box.items 38+units(\'ab\')])',
                   'return read(Pair[box.items 40] change(@box))')
          .replace('read=(pair:Pair)', 'read=(pair:Pair unused:int64)')
          .replace('forward=', 'change=(@box:Box):>int64=>{box.items.clear return 0}\nforward=')]


@pytest.mark.parametrize('source', CASES)
def test_conversions_preserve_unrelated_loan(tmp_path, source):
    execute(tmp_path, 'conversion-loan', codegen(SrcFile(None, source), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_conversion_loan_keeps_raw_and_write_boundaries(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_conversion_storage_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
