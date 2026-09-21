"""Clearing drops elements, retains the builtin's length fact and borrows once."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
ERRORS = [
    'main=():>int64=>{const items:array<array<int64>>=[[1]] items[0].clear return 42}',
    'main=():>int64=>{let items:array<array<int64 length=1>>=[[1]] items[0].clear return 42}',
]


@pytest.mark.parametrize('source,diagnostic', list(zip(ERRORS, ['const', 'exact-length'])))
def test_projected_method_preserves_storage_contracts(source, diagnostic):
    with pytest.raises(ReportException, match=diagnostic):
        codegen(SrcFile(None, source))


def test_resource_array_clear(tmp_path):
    execute(tmp_path, 'array-clear', codegen(SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_resource_array_clear.dewy'), debug_locations=False))


def test_native_resource_array_clear(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/lifecycle_resource_array_clear.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=ERRORS)
