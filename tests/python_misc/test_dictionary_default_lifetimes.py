"""A dictionary lookup cannot lend a temporary fallback past its cleanup."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/dictionary_default_lifetimes.dewy').read_text()


def test_temporary_record_default_survives_the_lookup_statement(tmp_path):
    execute(tmp_path, 'record-default', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_temporary_record_default(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
