"""A loop replacement must not reuse storage still owned by the previous value."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/fixed_array_replacements.dewy').read_text()


def test_fixed_array_replacement_storage(tmp_path):
    execute(tmp_path, 'fixed-replacement', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_fixed_array_replacement_storage(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
