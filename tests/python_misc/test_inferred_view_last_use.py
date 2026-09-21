"""Unwritten locals use a shorter borrow proof or retain independent values."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


BODIES = [
    'const view=rows[0] let answer=view.value rows.clear() return answer',
    'rows[0].value=42 const view=rows[0] let answer=view.value rows.clear() return answer',
    'const view=rows[0] const items=view.items let answer=view.value '
    'if items.length>?0 {if items[0] not=?7 return 1} rows.clear() return answer',
    # Owner changes during a live snapshot demand an independent copy.
    'const view=rows[0] rows.clear() return view.value',
    'const view=rows[0] const child=view rows[0].value=0 return child.value',
    'const view=rows[0] let answer:int64=0 loop i in 0..2 {answer=view.value rows[0].value=0} return answer',
    'let saved=Box[0 []] const view=rows[0] saved=view rows.clear() return saved.value',
]


@pytest.mark.parametrize('declaration', ['const', 'let'])
@pytest.mark.parametrize('body', BODIES)
def test_short_lifetimes_and_copy_fallback(tmp_path, body, declaration):
    body = body.replace('const ', declaration+' ')
    source = SrcFile(None, 'Box:type=[value:int64 items:array<int64>] '
                     'main=():>int64=>{let rows:array<Box>=[[42 [7]]] '+body+'}')
    execute(tmp_path, 'inferred-last-use', codegen(source, debug_locations=False))


@pytest.mark.parametrize('declaration', ['const', 'let'])
def test_strict_copy_policy_does_not_turn_conflicting_inference_into_aliasing(declaration):
    source = SrcFile(None, '$explicit_copies\nBox:type=[value:int64 items:array<int64>] '
                     'main=():>int64=>{let rows:array<Box>=[[42 [7]]] '
                     f'{declaration} view=rows[0] rows.clear() return view.value}}')
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(source)


def test_inferred_views_allocate_nothing_and_retain_nothing(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/inferred_view_last_use.dewy'
    execute(tmp_path, 'inferred-view-lifetime', codegen(SrcFile.from_path(source), debug_locations=False))


def test_inferred_let_views_allocate_nothing_and_retain_nothing(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/inferred_let_view_last_use.dewy'
    execute(tmp_path, 'inferred-let-lifetime', codegen(SrcFile.from_path(source), debug_locations=False))


def test_native_inferred_let_views(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = Path(__file__).resolve().parents[1] / 'fixtures/inferred_let_view_last_use.dewy'
    independent = 'Box:type=[value:int64 items:array<int64>] main=():>int64=>{let rows:array<Box>=[[42 [7]]] let view=rows[0] rows.clear() return view.value}'
    prefix = 'Box:type=[value:int64 items:array<int64>] main=():>int64=>{let rows:array<Box>=[[42 [7]]] '
    cases = [source.read_text(), independent,
             *(prefix+body.replace('const ', 'let ')+'}' for body in BODIES),
             prefix+'let view=rows[0] view.value=7 return rows[0].value}',
             prefix+'let view=rows[0] if view.items.length>?0 {view.items[0]=9} if rows[0].items.length>?0 {return rows[0].items[0]+35} return 1}',
             prefix+'let view=rows[0] read=():>int64=>view.value rows.clear() return read()}']
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=cases,
                          errors=['$explicit_copies\n'+independent])
