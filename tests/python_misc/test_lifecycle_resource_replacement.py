"""A replacement ends the old owner's lifetime after evaluating the new value."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
ERROR = """let changed:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{changed=1}
]
probe=():>void=>{changed=0 let owner=Handle[1] owner=Handle[2] $assert changed=?0}
"""


def test_replacement_cleanup_invalidates_facts():
    with pytest.raises(ReportException, match='assert'):
        codegen(SrcFile(None, ERROR))


def test_resource_replacement(tmp_path):
    execute(tmp_path, 'replacement', codegen(SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_resource_replacement.dewy'), debug_locations=False))


def test_native_resource_replacement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/lifecycle_resource_replacement.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[ERROR])
