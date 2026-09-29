"""Narrowed reads do not alter the layout or ownership of assignment slots."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/write_destination_facts.dewy'


def test_write_destination_facts(tmp_path):
    execute(tmp_path, 'write-destination-facts', codegen(SrcFile.from_path(FIXTURE), debug_locations=False))


def test_native_write_destination_facts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text()], errors=[])
