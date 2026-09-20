"""Read-only union views retain the cell and active payload's owner."""
from pathlib import Path

import pytest
from dewy.reporting import ReportException

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_union_and_string_views(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/explicit_union_views.dewy')
    execute(tmp_path, 'union-views', codegen(source, debug_locations=False))


@pytest.mark.parametrize('source', [
    'f=(value:string):>int64=>{const view=@value return view.length} main=():>int64=>f("{42}")+40',
    "f=(value:'a'|'bb'):>int64=>{const view=@value return view.length} main=():>int64=>f('bb')+40",
    'f=(value:int64|none):>int64=>{const view=@value if view is? none return 0 return view} main=():>int64=>f(42)',
])
def test_other_view_representations(tmp_path, source):
    execute(tmp_path, 'other-views', codegen(SrcFile(None, source), debug_locations=False))


def test_union_owner_write_cannot_silently_copy():
    source = SrcFile(None, 'Box:type=[value:int64] main=():>int64=>{'
                     'let owner:array<Box|none length=1>=[Box[42]] const view=@owner[0] '
                     'owner[0]=none if view is? none return 1 return view.value}')
    with pytest.raises(ReportException, match='cannot prove required local view'):
        codegen(source)



def test_view_does_not_hide_place_reads_from_effect_contracts():
    source = SrcFile(None, 'Box:type=[value:int64] '
                     'f=(@box:Box):>int64 & no_effects=>{const view=@box return view.value} '
                     'main=():>int64=>42')
    with pytest.raises(ReportException, match='effect contract'):
        codegen(source)


def test_string_union_length_without_a_view(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/string_union_length.dewy')
    execute(tmp_path, 'string-union-length', codegen(source, debug_locations=False))


def test_cold_string_queries_are_effect_free(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/cold_string_length.dewy')
    execute(tmp_path, 'cold-string-length', codegen(source, debug_locations=False))
