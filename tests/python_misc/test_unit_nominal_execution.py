from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute


def test_empty_nominal_values_keep_imported_identity(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/unit_nominal_values.dewy'
    execute(tmp_path, 'unit-nominal-values', codegen(SrcFile.from_path(fixture)))
