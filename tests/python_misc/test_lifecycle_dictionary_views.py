"""Dictionary snapshots own live values and preserve logical component hooks."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
CASES = [(ROOT / 'tests/fixtures/lifecycle_dictionary_views.dewy').read_text()]
ERRORS = [
    '''Handle=type of [id:int64 $__drop__ release=():>void=>{}]
main=():>int64=>{let d:dict<int64 Handle>=[1->Handle[10]] let values=d.values return 42}''',
    CASES[0].replace('work=():>int64=>', 'work=():>int64 & no_effects=>'),
]

@pytest.mark.parametrize('source', CASES)
def test_resource_dictionary_views(tmp_path, source):
    execute(tmp_path, 'views', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_resource_dictionary_view_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)

def test_native_resource_dictionary_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
