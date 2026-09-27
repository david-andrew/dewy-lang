"""Decoded string payloads survive their producing frame and are released."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/decoded_string_escapes.dewy'


def test_decoded_strings_escape_in_owning_cells(tmp_path):
    execute(tmp_path, 'decoded-escapes', codegen(SrcFile.from_path(FIXTURE)))


def test_native_decoded_strings_escape_in_owning_cells(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text()], errors=[])
