"""Implicit error returns release the same owners as explicit returns."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_propagation_cleanup(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_propagation_cleanup.dewy')
    execute(tmp_path, 'propagation-cleanup', codegen(source, debug_locations=False))


def test_native_propagation_cleanup(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/lifecycle_propagation_cleanup.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])
