"""An explicit local view demands stable storage; ordinary escapes stay values."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_explicit_local_views(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/explicit_local_views.dewy')
    execute(tmp_path, 'local-views', codegen(source, debug_locations=False))


def test_local_view_reports_conflicting_write():
    source = SrcFile.from_path(ROOT / 'tests/fixtures/explicit_local_view_write_rejected.dewy')
    with pytest.raises(ReportException, match='cannot prove required local view') as caught:
        codegen(source)
    assert 'this write or mutable place conflicts' in str(caught.value)
    assert 'boxes[0].value=99' in str(caught.value)


@pytest.mark.parametrize('code,diagnostic', [
    ('const x=@Box[42]', 'stored value'),
    ('const x=@42', 'stored value'),
    ('let x=@boxes[0]', 'mutable local places'),
    ('const x=@boxes[0] touch(@boxes) x.value;', 'cannot prove required local view'),
    ('const x=@boxes[0] boxes.push(Box[7]) x.value;', 'cannot prove required local view'),
])
def test_local_view_rejections(code, diagnostic):
    source = SrcFile(None, 'Box:type=[value:int64] touch=(@xs:array<Box>):>void=>{xs.push(Box[1])} '
                     'main=():>int64=>{let boxes:array<Box>=[Box[42]] '+code+' return 42}')
    with pytest.raises(ReportException, match=diagnostic):
        codegen(source)


def test_readonly_owner_and_parenthesized_view(tmp_path):
    source = SrcFile(None, 'Box:type=const [value:int64] main=():>int64=>{'
                     'const boxes:array<Box>=[Box[42]] const value=(@(boxes[0])) return value.value}')
    execute(tmp_path, 'const-views', codegen(source, debug_locations=False))


def test_nested_place_argument_keeps_its_write_barrier():
    source = SrcFile(None, 'Box:type=[value:int64] index=(@n:int64):>int64=>{n=0 return n} '
                     'main=():>int64=>{const n:int64=0 let boxes:array<Box>=[Box[42]] '
                     'const view=@boxes[index(@n)] return view.value}')
    with pytest.raises(ReportException, match='const'):
        codegen(source)


def test_fixed_array_view_retains_raw_storage_representation(tmp_path):
    source = SrcFile(None, 'main=():>int64=>{let source=[20 22] const view=@source '
                     'return view[0]+view[1]}')
    execute(tmp_path, 'raw-view', codegen(source, debug_locations=False))


def test_no_copy_fallback_for_an_explicit_demand(monkeypatch):
    from dewy.backend.udewy.lowering_objects import _ObjectLowering
    monkeypatch.setattr(_ObjectLowering, '_borrowed_route_local', lambda *_: False)
    source = SrcFile(None, 'Box:type=[value:int64] main=():>int64=>{let box=Box[42] '
                     'const view=@box return view.value}')
    with pytest.raises(ReportException, match='cannot prove required local view'):
        codegen(source)


def test_view_index_is_evaluated_once(tmp_path):
    source = SrcFile(None, '''
Box:type=[value:int64]
index=(@visits:int64):>int64<v=>v=?0>=>{visits+=1 return 0}
main=():>int64=>{
    let visits:int64=0
    let boxes:array<Box length=1>=[Box[42]]
    const view=@boxes[index(@visits)]
    $runtime_assert visits=?1
    return view.value
}
''')
    execute(tmp_path, 'view-index-once', codegen(source, debug_locations=False))
