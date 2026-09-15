"""Optional and general union strings need payload tests, not just tag tests."""
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_dict_rebuild_helpers import ROOT, check_generated


def test_union_string_payload_tests(tmp_path):
    source = ROOT / 'tests/fixtures/union_string_tests.dewy'
    check_generated(codegen(SrcFile.from_path(source), debug_locations=False), tmp_path / 'string-tests.udewy')
