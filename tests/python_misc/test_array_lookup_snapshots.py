"""Lowered loads keep their borrowing role at an optional value boundary."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1]/'fixtures/array_lookup_snapshots.dewy').read_text()
CASES = [SOURCE, SOURCE.replace('fetch(table)', 'table.get(0)'),
         SOURCE.replace('dict<int64 array<int64>>', 'dict<int64 array<int64>|none>')
         .replace('0 in? table and ', '0 in? table and table[0] isnt? none and ')]


@pytest.mark.parametrize('source', CASES)
def test_array_lookup_keeps_its_owner(tmp_path, source):
    output = codegen(SrcFile(None, source), debug_locations=False)
    execute(tmp_path, 'array-lookup', output)


def test_array_lookup_reports_its_snapshot():
    codegen(SrcFile(None, SOURCE), debug_locations=False)
    assert any(note.srcfile.path is None and note.kind == 'array'
               and note.site == 'looked up with get' and note.runtime_sized
               for note in lower.last_copy_notes)


def test_native_array_lookup_snapshots(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
