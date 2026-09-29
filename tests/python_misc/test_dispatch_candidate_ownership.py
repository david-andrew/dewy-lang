"""Ordered dispatch retains only the chosen owning promotion plan."""
from pathlib import Path

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/fixtures/dispatch_candidate_ownership.dewy'


def test_ordered_dispatch_candidate_ownership(tmp_path):
    generated = codegen(SrcFile.from_path(SOURCE), debug_locations=False)
    # Selection transfers its winner, and generic instantiation transfers
    # disjoint inference fields to the owning substitution parameters.
    notes = [note for note in lower.last_copy_notes
             if note.srcfile.path and note.srcfile.path.name == 'dispatch.dewy'
             and note.runtime_sized and not note.explicit and not note.policy_exempt]
    assert not notes
    execute(tmp_path, 'dispatch-candidates', generated)


def test_native_ordered_dispatch_candidate_ownership(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = SOURCE.read_text().replace('p"../../dewy/', f'p"{ROOT}/dewy/')
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])
