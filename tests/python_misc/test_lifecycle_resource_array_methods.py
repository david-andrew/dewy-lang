"""Resource array insertions, removals and discarded fresh owners."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
OWNER = """let changed:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{changed=1}
]
"""
ERRORS = [
    OWNER + 'probe=():>void & allocates=>{let items:array<Handle>=[Handle[1]] items.pop;}',
    OWNER + 'probe=():>void=>{changed=0 let items:array<Handle>=[Handle[1]] items.pop; $assert changed=?0}',
]


@pytest.mark.parametrize('source,diagnostic', list(zip(ERRORS, ['effect contract', 'assert'])))
def test_discarded_element_cleanup_is_checked(source, diagnostic):
    with pytest.raises(ReportException, match=diagnostic):
        codegen(SrcFile(None, source))


def test_resource_array_methods(tmp_path):
    execute(tmp_path, 'array-methods', codegen(SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_resource_array_methods.dewy'), debug_locations=False))


def test_native_resource_array_methods(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/lifecycle_resource_array_methods.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=ERRORS)
