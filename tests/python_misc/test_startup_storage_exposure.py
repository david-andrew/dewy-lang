"""Startup address exposure participates in the ordinary storage proof."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/startup_storage_exposure.dewy'
SOURCE = FIXTURE.read_text()
CASES = [SOURCE,
    SOURCE.replace('let pointer=__load_i64__(values transmute int64)',
                   'let pointer:int64=0\npointer=__load_i64__(values transmute int64)'),
    SOURCE.replace('let answer=read(values)',
                   'let snapshot=values\n    let answer=read(snapshot)'),
]
UNGUARDED = SOURCE.replace('values.length>?0 and ', '')


@pytest.mark.parametrize('source', CASES)
def test_startup_exposure_preserves_value_argument(tmp_path, source):
    execute(tmp_path, 'startup-exposure', codegen(SrcFile(None, source), debug_locations=False))


def test_exposed_global_extent_needs_current_evidence():
    with pytest.raises(UserError, match='index is not proven in bounds'):
        codegen(SrcFile(None, UNGUARDED), debug_locations=False)


def test_native_startup_exposure_preserves_value_argument(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[UNGUARDED])
