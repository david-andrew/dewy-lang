"""Inherited moves adopt added owners; only the original hook's fields remain."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_inherited_move_components.dewy'
ERRORS = [
    # Composition does not turn an inherited copy into ownership transfer.
    'Token=type of [id:int64 $__drop__ release=():>void=>{}]\n'
    'Parent=type of [value:int64 $__copy__ duplicate=():>Parent=>Parent[value]]\n'
    'Derived=type of Parent & [added:Token]\n'
    'main=():>int64=>{let source=Derived[42 Token[3]] let copied=source.copy() return copied.value}',
    # A second use that needs independent resources still cannot copy them.
    'Token=type of [id:int64 $__drop__ release=():>void=>{}]\n'
    'Parent=type of [value:int64 $__move__ relocate=():>Parent=>Parent[value]]\n'
    'Derived=type of Parent & [added:Token]\n'
    'main=():>int64=>{let source=Derived[42 Token[3]] let saved=source '
    'saved.added.id=4 return source.added.id}',
]


def test_added_resource_fields_move_once(tmp_path):
    execute(tmp_path, 'inherited-move-components', codegen(SrcFile.from_path(FIXTURE), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_move_composition_does_not_authorize_independent_copies(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_inherited_move_components(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[FIXTURE.read_text()], errors=ERRORS)
