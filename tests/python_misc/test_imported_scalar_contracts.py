"""An imported mutable scalar's initializer is not its permanent value."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures/imported_scalar_contracts'
CASES = [name + '.dewy' for name in ('selective', 'namespace', 'splat')]


@pytest.mark.parametrize('name', CASES)
def test_imported_scalar_contract(tmp_path, name):
    execute(tmp_path, name, codegen(SrcFile.from_path(FIXTURES / name), debug_locations=False))


def test_native_imported_scalar_contracts(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    (tmp_path / 'state.dewy').write_text((FIXTURES / 'state.dewy').read_text())
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[(FIXTURES / name).read_text() for name in CASES], errors=[])
