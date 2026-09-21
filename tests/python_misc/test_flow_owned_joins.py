"""Flow joins preserve owning storage across record/cell representations."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/flow_owned_joins.dewy').read_text()


def test_owned_flow_joins(tmp_path):
    execute(tmp_path, 'flow-joins', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_owned_flow_joins(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
