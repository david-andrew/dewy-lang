"""Report property snapshots once and honor an explicit copy at that boundary."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from test_scalar_projection import execute

FIXTURE = (Path(__file__).resolve().parents[1] / 'fixtures/explicit_entry_snapshots.dewy').read_text()
KEYS = '''main=():>int64=>{
    let table:dict<string int64>=['answer'->42]
    let snapshot=table.keys
    table.clear
    return if 'answer' in? snapshot 42 else 1
}'''
VALUES = KEYS.replace('table.keys', 'table.values').replace("'answer' in? snapshot", 'snapshot.length=?1 and snapshot[0]=?42')
SET_VALUES = '''main=():>int64=>{
    let source:set<int64>=set[42]
    let snapshot=source.values
    source.clear
    return if snapshot.length=?1 snapshot[0] else 1
}'''
CASES = [KEYS, VALUES, SET_VALUES]


@pytest.mark.parametrize('source', CASES)
def test_entry_snapshot_has_one_source_copy(tmp_path, source):
    text = codegen(SrcFile(None, source), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.site.startswith('materialized from')]
    assert len(notes) == 1 and not notes[0].explicit
    execute(tmp_path, 'entry-snapshot', text)
    with pytest.raises(UserError, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)


@pytest.mark.parametrize('source', CASES)
def test_explicit_entry_snapshot(tmp_path, source):
    source = source.replace('.keys', '.keys.copy()').replace('.values', '.values.copy()')
    text = codegen(SrcFile(None, '$explicit_copies\n' + source), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.site.startswith('materialized from')]
    assert len(notes) == 1 and notes[0].explicit
    execute(tmp_path, 'explicit-entry-snapshot', text)


def test_explicit_entry_snapshot_cleanup(tmp_path):
    execute(tmp_path, 'entry-snapshot-lifetime', codegen(SrcFile(None, FIXTURE), debug_locations=False))


def test_native_entry_snapshot_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    explicit = ['$explicit_copies\n' + source.replace('.keys', '.keys.copy()').replace('.values', '.values.copy()') for source in CASES]
    check_structural_text(build_program_driver(tmp_path), tmp_path,
        cases=CASES + explicit + [FIXTURE, TEMPORARY], errors=['$explicit_copies\n' + source for source in CASES])


TEMPORARY = (Path(__file__).resolve().parents[1] / 'fixtures/temporary_entry_snapshots.dewy').read_text()


def test_temporary_entry_snapshot_cleanup(tmp_path):
    execute(tmp_path, 'temporary-entry-snapshot', codegen(SrcFile(None, TEMPORARY), debug_locations=False))
