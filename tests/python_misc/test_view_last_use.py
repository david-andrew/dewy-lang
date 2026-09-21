"""Required views end after all dependent aliases, with control flow intact."""
import pytest
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from tests.python_misc.test_scalar_projection import execute


def program(body):
    return SrcFile(None, 'Box:type=[value:int64]\nmain=():>int64=>{\n'
                   'let rows:array<Box>=[[42]]\n' + body + '\n}')


@pytest.mark.parametrize('body', [
    'rows[0].value=42 const view=@rows[0] let answer=view.value rows.clear() return answer',
    'const view=@rows[0] const child=@view let answer=child.value rows.clear() return answer',
    'const view=@rows[0] const child=view let answer=child.value rows.clear() return answer',
    'const view=@rows[0] let answer:int64=0 if rows.length>?0 {answer=view.value} rows.clear() return answer',
    'const view=@rows[0] let answer:int64=0 loop i in 0..1 {answer=view.value} rows.clear() return answer',
    'const view=@rows[0] let saved=view.copy() rows.clear() return saved.value',
    'const view=@rows[0] rows.clear() return 42',
    'let answer:int64=0 loop i in 0..0 {const view=@rows[0] answer=view.value rows[0].value=0} return answer',
])
def test_owner_can_change_after_last_view_use(tmp_path, body):
    execute(tmp_path, 'last_use', codegen(program(body), debug_locations=False))


@pytest.mark.parametrize('body', [
    'const view=@rows[0] const child=@view rows.clear() return child.value',
    'const view=@rows[0] const child=view rows.clear() return child.value',
    'const view=@rows[0] const child=@view const grandchild=@child rows.clear() return grandchild.value',
    'const view=@rows[0] let answer:int64=0 loop i in 0..2 {answer=view.value rows[0].value=0} return answer',
    'const view=@rows[0] let answer=view.value rows[0].value=0 if rows.length>?0 {answer=view.value} return answer',
    'let saved=Box[0] const view=@rows[0] saved=view rows.clear() return saved.value',
])
def test_derived_aliases_and_repeated_reads_keep_view_live(body):
    with pytest.raises(ReportException, match='required local view'):
        codegen(program(body))


def test_conflict_diagnostic_ignores_writes_before_the_view():
    source = program('rows[0].value=1\nconst view=@rows[0]\nrows[0].value=2\nreturn view.value')
    with pytest.raises(ReportException) as error:
        codegen(source)
    assert 'this write or mutable place conflicts' in str(error.value)
    assert 'rows[0].value=2' in str(error.value)


def test_last_use_view_has_no_copies_or_retained_storage(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'fixtures/view_last_use.dewy'
    execute(tmp_path, 'last_use_lifetime', codegen(SrcFile.from_path(source), debug_locations=False))
