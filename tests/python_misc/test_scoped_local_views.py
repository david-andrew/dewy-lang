"""Lexical view lifetimes preserve value semantics outside the borrowing block."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


@pytest.mark.parametrize('inside', [
    'const view=@rows[0] answer=view.value',
    'const view=@rows[0] printl(view.value) answer=view.value',
    'if rows.length>?0 {const view=@rows[0] answer=view.value}',
    'const view=@rows[0] {const child=@view answer=child.value}',
])
def test_owner_changes_outside_required_scope(tmp_path, inside):
    source = SrcFile(None, 'Box:type=[value:int64]\nmain=():>int64=>{'
                     'let rows:array<Box>=[] rows.push([42]) let answer:int64=0\n'
                     '{'+inside+'}\nrows.clear() return answer}')
    execute(tmp_path, 'scoped', codegen(source, debug_locations=False))


@pytest.mark.parametrize('inside', [
    'const view=@rows[0] rows.clear() answer=view.value',
    'const view=@rows[0] {const child=@view rows.clear() answer=child.value}',
    'const view=@rows[0] rows[0].value=7 answer=view.value',
    'const view=@rows[0] clear(@rows) answer=view.value',
])
def test_required_scope_still_rejects_conflicts(inside):
    source = SrcFile(None, 'Box:type=[value:int64]\nclear=(@xs:array<Box>):>void=>{xs.clear()}\n'
                     'main=():>int64=>{let rows:array<Box>=[] rows.push([42]) let answer:int64=0\n'
                     '{'+inside+'}\nrows.clear() return answer}')
    with pytest.raises(ReportException, match='required local view'):
        codegen(source)


def test_returned_value_is_independent_of_the_scoped_view(tmp_path):
    source = SrcFile(None, '''Box:type=[value:int64]
main=():>int64=>{
    let rows:array<Box>=[]
    rows.push([42])
    let saved={const view=@rows[0] view}
    rows[0].value=7
    rows.clear()
    return saved.value
}''')
    execute(tmp_path, 'saved', codegen(source, debug_locations=False))


def test_scoped_view_has_no_copy_or_retained_storage(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/scoped_local_views.dewy'
    execute(tmp_path, 'scoped_lifetime', codegen(SrcFile.from_path(source), debug_locations=False))


def test_addressed_owner_needs_more_than_the_lexical_proof():
    source = SrcFile(None, 'Box:type=[value:int64]\n'
                     'change=(@rows:array<Box>):>void=>{rows.push([9])}\n'
                     'main=():>int64=>{let rows:array<Box>=[[42]] change(@rows) '
                     'if rows.length=?0 return 0 let answer:int64=0 {const view=@rows[0] answer=view.value} return answer}')
    with pytest.raises(ReportException, match='required local view'):
        codegen(source)
