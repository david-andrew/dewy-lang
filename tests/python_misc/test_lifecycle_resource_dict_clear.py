"""Dictionary clear drops values once before releasing table storage."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_resource_dict_clear.dewy').read_text()
ERRORS = [
    SOURCE.replace('let items:dict', 'const items:dict'),
    # Generated drop calls must be visible to effect checking.
    SOURCE.replace('exercise=():>int64=>', 'exercise=():>int64 & no_effects=>'),
]


def test_resource_dictionary_clear(tmp_path):
    execute(tmp_path, 'dictionary-clear', codegen(SrcFile(None, SOURCE), debug_locations=False))


@pytest.mark.parametrize('source', ERRORS)
def test_resource_dictionary_clear_obligations(source):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_resource_dictionary_clear(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=ERRORS)
