"""Inferred metadata alone must not trigger whole-program effect obligations."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/effect_validation_gate.dewy'


def test_effect_validation_gate(tmp_path):
    execute(tmp_path, 'effect-validation-gate', codegen(SrcFile.from_path(FIXTURE)))


def test_native_effect_validation_gate(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    kernel = FIXTURE.read_text().replace('../../dewy/', str(ROOT / 'dewy') + '/')
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[kernel, (ROOT / 'tests/fixtures/generic_effect_guarantees.dewy').read_text()],
                          errors=[(ROOT / 'tests/fixtures/inferred_callable_lifecycle_rejected.dewy').read_text(),
                                  (ROOT / 'tests/fixtures/generic_effect_guarantees_rejected.dewy').read_text()])
