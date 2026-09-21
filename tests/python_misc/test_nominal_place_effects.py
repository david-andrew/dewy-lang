"""A wider nominal place borrows fields; it cannot replace the child owner."""
import pytest

from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check


TYPES = 'Base=type of [token:int64]\nDerived=type of Base & [extra:int64]\n'


@pytest.mark.parametrize('helpers, call', [
    ('replace=(@p:Base):>void=>{p=Base[0]}', 'replace(@d)'),
    ('replace=(@p:Base):>void=>{p=Base[0]}\nforward=(@p:Base):>void=>replace(@p)', 'forward(@d)'),
    ('replace=(@p:Base):>void=>{let inner=():>void=>{p=Base[0]} inner()}', 'replace(@d)'),
    ('replace=(@p:Base):>void=>{p=Base[0]}', 'replace(p=@d)'),
])
def test_parent_place_cannot_replace_child(helpers, call):
    source = TYPES + helpers + f'\nf=():>void=>{{let d=Derived[42 1] {call}}}'
    with pytest.raises(ReportException, match='parent place may replace or escape the child'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_unknown_callback_cannot_rebind_a_child_through_its_parent():
    source = TYPES + 'f=(callback:(@p:Base):>void):>void=>{let d=Derived[42 1] callback(@d)}'
    with pytest.raises(ReportException, match='parent place may replace or escape the child'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_overloaded_parent_replacement_is_rejected():
    # Overload dispatch currently requires an exact place parameter type;
    # this path rejects before the transitive parent-place proof runs.
    source = TYPES + 'replace=(n:int64):>void=>{}\nreplace &= (@p:Base):>void=>{p=Base[0]}\nf=():>void=>{let d=Derived[42 1] replace(@d)}'
    with pytest.raises(ReportException, match='no matching method for call'):
        check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


@pytest.mark.parametrize('helpers, call', [
    ('update=(@p:Base):>void=>{p.token=0}', 'update(@d)'),
    ('update=(@p:Base):>void=>{p.token=0}\nforward=(@p:Base):>void=>update(@p)', 'forward(@d)'),
    ('read=(@p:Base):>Base=>p', 'let copy=read(@d)'),
    ('replace=(@p:Derived):>void=>{p=Derived[0 2]}', 'replace(@d)'),
])
def test_field_updates_and_independent_values_preserve_identity(helpers, call):
    source = TYPES + helpers + f'\nf=():>void=>{{let d=Derived[42 1] {call}}}'
    check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def test_imported_parent_helper_is_analyzed_in_its_defining_graph(tmp_path):
    (tmp_path / 'parent.dewy').write_text('let Base=type of [token:int64]\nlet update=(@p:Base):>void=>{p.token=42}')
    source = tmp_path / 'main.dewy'
    source.write_text('from p"parent.dewy" import Base, update\nDerived=type of Base & [extra:int64]\nf=():>void=>{let d=Derived[0 1] update(@d)}')
    check.typecheck_and_resolve(SrcFile.from_path(source))
