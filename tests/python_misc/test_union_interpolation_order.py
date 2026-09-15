"""Union formatting captures values at their expression evaluation point."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_dict_rebuild_helpers import check_generated

ROOT = Path(__file__).resolve().parents[2]


def test_union_interpolation_evaluation_order(tmp_path):
    source = ROOT / 'tests/fixtures/union_interpolation_order.dewy'
    check_generated(codegen(SrcFile.from_path(source), debug_locations=False),
                    tmp_path / 'interpolation.udewy')
