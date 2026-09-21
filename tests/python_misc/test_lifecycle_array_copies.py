"""Array copies construct resource elements through checked copy hooks."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_array_copies.dewy').read_text()
ERRORS = ['$explicit_copies\n' + SOURCE]


def test_array_copies(tmp_path):
    execute(tmp_path, 'array-copies', codegen(SrcFile(None, SOURCE), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_array_copies_report_implicit_cost(source):
    with pytest.raises(ReportException, match='explicit_copies'):
        codegen(SrcFile(None, source))


def test_native_array_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=ERRORS)
