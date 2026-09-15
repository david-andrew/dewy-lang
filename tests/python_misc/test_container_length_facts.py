"""Dictionary and set lengths carry the same nonnegative fact as arrays."""
from pathlib import Path
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import TypeCheckError
from test_dict_rebuild_helpers import check_generated

ROOT = Path(__file__).resolve().parents[2]


def test_container_lengths_are_addresses(tmp_path):
    source = ROOT / 'tests/fixtures/container_length_facts.dewy'
    check_generated(codegen(SrcFile.from_path(source), debug_locations=False),
                    tmp_path / 'lengths.udewy')


def test_a_negative_live_count_cannot_enter_a_dictionary():
    with pytest.raises(TypeCheckError, match='refinement'):
        codegen(SrcFile(None, 'main=():>int64=>{let d:dict<int64 int64>=[] d.live=-1 return 0}'))
