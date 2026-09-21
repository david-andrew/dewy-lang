"""Numeric printing and value casts respect the read's storage representation."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/numeric_union_printing.dewy'
OUTPUT = '3\n7\nnone\n-9223372036854775808\n9223372036854775807\n18446744073709551615\n0\n123456789012345678901234567890\n'


def test_hosted_numeric_union_printing(tmp_path):
    for result in execute(tmp_path, 'numbers', codegen(SrcFile.from_path(SOURCE), debug_locations=False)):
        assert result.stdout == OUTPUT


def test_native_numeric_union_printing(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text

    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE.read_text()], errors=[], outputs=[OUTPUT])
