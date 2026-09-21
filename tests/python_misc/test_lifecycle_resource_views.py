from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_resource_views.dewy').read_text()



def test_readonly_resource_aliases_share_one_owner(tmp_path):
    execute(tmp_path, 'resource-views', codegen(SrcFile(None, SOURCE), debug_locations=False))


def test_native_readonly_resource_aliases(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=[])
