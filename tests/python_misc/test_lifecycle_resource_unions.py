"""Only a union's active alternative owns storage and runs lifecycle hooks."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import check
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ['lifecycle_resource_unions', 'optional_receiver_lifetimes']
OWNER = """let changed:int64=0
Handle=type of [token:int64
$__drop__
release=():>void=>{changed=1}
]
"""
ERRORS = [
    OWNER + 'consume=(owner:Handle?):>void & no_effects=>{}',
    OWNER + 'consume=(owner:Handle?):>void=>{}\nmain=():>int64=>{changed=0 consume(Handle[42]); $assert changed=?0 return 42}',
]


@pytest.mark.parametrize('name', FIXTURES)
def test_resource_union_lifetimes(tmp_path, name):
    execute(tmp_path, name, codegen(SrcFile.from_path(ROOT / f'tests/fixtures/{name}.dewy'), debug_locations=False))


@pytest.mark.parametrize('source,diagnostic', list(zip(ERRORS, ['effect contract', 'assert'])))
def test_union_cleanup_is_checked(source, diagnostic):
    for compile_ in (check.typecheck_and_resolve, codegen):
        with pytest.raises(ReportException, match=diagnostic):
            compile_(SrcFile(None, source))


def test_native_resource_union_lifetimes(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    sources = [(ROOT / f'tests/fixtures/{name}.dewy').read_text() for name in FIXTURES]
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=sources, errors=ERRORS)
