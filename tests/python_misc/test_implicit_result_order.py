"""Implicit function results do not skip subsequent statements."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_trailing_statements_and_result_lifetimes(tmp_path):
    execute(tmp_path, 'result-order', codegen(SrcFile.from_path(ROOT / 'tests/fixtures/implicit_result_order.dewy'), debug_locations=False))


def test_native_trailing_statements_and_result_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/implicit_result_order.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])
