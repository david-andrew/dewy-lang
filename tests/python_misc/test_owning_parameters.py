from pathlib import Path
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('name', ['native_owned_parameters', 'owning_array_parameters', 'strict_copy_owned_parameter', 'array_parameter_lifetimes'])
def test_direct_parameter_ownership(tmp_path, name):
    fixture = Path(__file__).resolve().parents[1] / f'fixtures/{name}.dewy'
    execute(tmp_path, name, codegen(SrcFile.from_path(fixture), debug_locations=False))
