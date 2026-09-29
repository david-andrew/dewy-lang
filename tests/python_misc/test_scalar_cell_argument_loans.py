"""Scalar union fields carry a tag and word, without a payload owner."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_nested_record_argument_loans import SOURCE

CELL = SOURCE.replace('Pair:type=[inner:Inner offset:int64]', 'Pair:type=[inner:Inner offset:int64?=none]')
CELL = CELL.replace('pair.inner.items.length+pair.inner.offset+pair.offset',
                    'pair.inner.items.length+pair.inner.offset+(if pair.offset is? none 20 else pair.offset)')
CASES = [CELL, CELL.replace('Pair[inner 20]', 'Pair[inner]'),
    CELL.replace('offset:int64?', 'offset:int64|bool').replace('=none]', '=false]')
        .replace('pair.offset is? none', 'pair.offset is? bool').replace('Pair[inner 20]', 'Pair[inner]')]
CASES.append(CELL.replace('forward=(inner:Inner)', 'forward=(inner:Inner extra:int64?=none)')
    .replace('Pair[inner 20]', 'Pair[inner extra]'))
# An array cell owns a payload, even though its outer storage is two words.
OWNED = SOURCE.replace('Pair:type=[inner:Inner offset:int64]', 'Pair:type=[inner:Inner offset:(array<int64>|none)]')
OWNED = OWNED.replace('pair.inner.items.length+pair.inner.offset+pair.offset',
                      'if pair.offset is? none 0 else pair.inner.items.length+pair.inner.offset+pair.offset.length*20')
OWNED = OWNED.replace('Pair[inner 20]', 'Pair[inner [20]]')

@pytest.mark.parametrize('source', CASES)
def test_scalar_cell_argument_loans(tmp_path, source):
    execute(tmp_path, 'scalar-cell-loan', codegen(SrcFile(None, source), debug_locations=False))


def test_owned_cell_keeps_its_storage_obligation():
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, OWNED), debug_locations=False)


def test_native_scalar_cell_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[OWNED])
