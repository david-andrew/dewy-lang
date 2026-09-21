"""Synthesized copies respect nested resource hooks and independent storage."""
from pathlib import Path
import subprocess
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_component_copies.dewy').read_text()
ERRORS = [
    '''let count:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{}
$__copy__
duplicate=():>Handle=>{count+=1 Handle[id]}
]
copy=(value:[child:Handle]):>[child:Handle] & no_effects=>value.copy()''',
    '''Handle=type of [id:int64
$__drop__
release=():>void=>{}
]
main=():>int64=>{let a=[child=Handle[42]] let b=a b.child.id=1 return a.child.id}''',
]


def test_component_copies(tmp_path):
    execute(tmp_path, 'component-copies', codegen(SrcFile(None, SOURCE), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_component_copies_preserve_effect_and_capability_checks(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source))


def test_native_component_copies(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    binary = build_program_driver(tmp_path)
    check_structural_text(binary, tmp_path, cases=[SOURCE], errors=ERRORS[:1])
    # General inferred ownership conflicts still use the lifecycle lowering
    # diagnostic; the shared checker helper only handles semantic errors.
    source = tmp_path / 'inferred-move-only.dewy'
    source.write_text(ERRORS[1])
    result = subprocess.run([binary, source, ROOT / 'library', tmp_path / 'prelude-cache'],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1 and 'Error' in result.stderr, result.stderr
