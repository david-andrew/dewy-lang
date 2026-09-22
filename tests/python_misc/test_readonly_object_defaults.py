"""Read-only supplied records borrow; omitted defaults own their cleanup."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/readonly_object_defaults.dewy').read_text()
CASES = [SOURCE,
    # The callback boundary still requires its own snapshot here. The callee
    # must borrow that supplied snapshot and leave its cleanup with the caller.
    SOURCE.replace('if read(box) not=?42', 'let getter=@read if getter(box.copy()) not=?42')
          .replace('_arena_allocated_bytes not=?before or ', ''),
]


@pytest.mark.parametrize('source', CASES)
def test_readonly_record_defaults_borrow_and_cleanup(source, tmp_path):
    execute(tmp_path, 'readonly-record-defaults', codegen(SrcFile(None, source)))


def test_native_readonly_record_defaults(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
