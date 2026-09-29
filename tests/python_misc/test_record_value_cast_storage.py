"""Logical record casts survive until their owning storage is selected."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
CURSOR = (ROOT / 'tests/fixtures/record_cursor_value_cast.dewy').read_text()
MUTATE = CURSOR.replace(
    'loop terminal is? Group {terminal=get(nodes terminal.child)}',
    'terminal.value=99',
)
DYNAMIC = CURSOR.replace('type of [value:int64]', 'type of [value:int64 items:array<int64>]') \
    .replace("Group[42 1] Other[3 'x']", "Group[42 [1 2] 1] Other[3 [4] 'x']")


@pytest.mark.parametrize('source', [CURSOR, MUTATE, DYNAMIC])
def test_record_cast_local_keeps_value_independence(tmp_path, source):
    execute(tmp_path, 'record-cast', codegen(SrcFile(None, source), debug_locations=False))


def test_record_cast_does_not_hide_an_implicit_copy():
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n' + DYNAMIC), debug_locations=False)


def test_native_record_cast_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[CURSOR, MUTATE, DYNAMIC],
                          errors=['$explicit_copies\n' + DYNAMIC])
