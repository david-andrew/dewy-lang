"""Facts see implicit ownership operations on the first checking pass."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('file_source', [False, True])
def test_implicit_effects_do_not_refute_a_later_guard(tmp_path, file_source):
    text = (ROOT / 'tests/fixtures/lifecycle_owning_parameters.dewy').read_text()
    assert 'drops not=?6 or values.length not=?2' in text
    if file_source:
        path = tmp_path / 'guard.dewy'
        path.write_text(text)
        source = SrcFile.from_path(path)
    else:
        source = SrcFile(None, text)
    checked = check.typecheck_and_resolve(source, include_prelude=True)
    assert checked.ownership_prepared
    execute(tmp_path, 'ownership-guard', codegen(source, debug_locations=False))


def test_temporary_copy_receivers_are_evaluated_and_dropped_once(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_temporary_copy_receivers.dewy')
    execute(tmp_path, 'temporary-copy-receivers', codegen(source, debug_locations=False))


def test_native_lifecycle_guard_and_temporary_receivers(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    sources = [ROOT / f'tests/fixtures/{name}.dewy' for name in
               ['lifecycle_owning_parameters', 'lifecycle_temporary_copy_receivers']]
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[source.read_text() for source in sources], errors=[])
