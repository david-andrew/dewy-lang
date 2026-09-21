"""Key probes borrow briefly; eager defaults must retain the earlier key."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/dictionary_key_borrows.dewy'


def test_dictionary_key_lifetime_and_probe_allocation(tmp_path):
    execute(tmp_path, 'dictionary-key-borrows', codegen(SrcFile.from_path(FIXTURE)))


def test_native_dictionary_key_lifetime_and_probe_allocation(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[FIXTURE.read_text()], errors=[])
