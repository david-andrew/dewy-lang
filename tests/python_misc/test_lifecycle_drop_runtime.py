"""Actual local owners release once, in scope order, before backing cleanup."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import check
from tests.python_misc.test_scalar_projection import execute


OWNER = '''TraceHandle=type of [token:int64
$__drop__
release=():>void=>{printl(token) token=0}
]
'''


@pytest.mark.parametrize('body,output', [
    ('let h=TraceHandle[42] return h.token', '42\n'),
    ('let h=TraceHandle[42] h.token', '42\n'),
    ('if true {let h=TraceHandle[42] h.token} else 0', '42\n'),
    ('let first=TraceHandle[1] let second=TraceHandle[2] return 42', '2\n1\n'),
    ('let outer=TraceHandle[1] {let inner=TraceHandle[2]} return 42', '2\n1\n'),
    ('let outer=TraceHandle[1] if true {let inner=TraceHandle[2] return 42} return 0', '2\n1\n'),
    ('let outer=TraceHandle[42] loop i in 0..3 {let inner=TraceHandle[i] '
     'if i=?1 {continue} if i=?2 {break}} return outer.token', '0\n1\n2\n42\n'),
])
def test_local_drop_order_and_control_flow(tmp_path, body, output):
    source = SrcFile(None, OWNER + 'main=():>int64=>{'+body+'}')
    for result in execute(tmp_path, 'drop-order', codegen(source, debug_locations=False)):
        assert result.stdout == output


def test_implicit_drop_effects_are_checked():
    source = SrcFile(None, OWNER + 'main=():>int64 & allocates=>{let h=TraceHandle[42] return 42}')
    with pytest.raises(ReportException, match='effect contract'):
        codegen(source)


@pytest.mark.parametrize('body', [
    'let h=TraceHandle[42] let other=h return other.token',
    'let h=TraceHandle[42] let read=():>int64=>h.token return read()',
    'let h=TraceHandle[42] let values=[h] return 42',
])
def test_unimplemented_transfers_remain_explicitly_rejected(body):
    with pytest.raises(ReportException, match='lifecycle ownership lowering'):
        codegen(SrcFile(None, OWNER + 'main=():>int64=>{'+body+'}'))


def test_drop_invalidates_facts_before_a_later_assertion():
    source = '''let total:int64=0
Handle=type of [token:int64
$__drop__
release=():>void=>{total=1}
]
main=():>int64=>{
    total=0
    {let h=Handle[42]}
    $assert total=?0
    return 42
}
'''
    # The source-only graph has not materialized the implicit write yet.
    check.typecheck_and_resolve(SrcFile(None, source))
    with pytest.raises(ReportException, match='prove|assert'):
        codegen(SrcFile(None, source))


def test_drop_effects_in_a_callee_invalidate_caller_facts():
    source = '''let total:int64=0
Handle=type of [token:int64
$__drop__
release=():>void=>{total=1}
]
dropper=():>void=>{let h=Handle[42]}
main=():>int64=>{total=0 dropper() $assert total=?0 return 42}
'''
    # The source-only graph has not materialized the implicit write yet.
    check.typecheck_and_resolve(SrcFile(None, source))
    with pytest.raises(ReportException, match='prove|assert'):
        codegen(SrcFile(None, source))


def test_parent_drop_runs_for_the_child_owner(tmp_path):
    source = SrcFile(None, OWNER + '''ExtraHandle=type of TraceHandle & [extra:int64]
main=():>int64=>{let child=ExtraHandle[40 2] return child.token+child.extra}
''')
    for result in execute(tmp_path, 'inherited-drop', codegen(source, debug_locations=False)):
        assert result.stdout == '40\n'


def test_imported_owner_keeps_its_implicit_drop_call(tmp_path):
    (tmp_path / 'owner.dewy').write_text(OWNER)
    source = tmp_path / 'main.dewy'
    source.write_text('from p"owner.dewy" import TraceHandle\nmain=():>int64=>{let h=TraceHandle[42] return h.token}')
    for result in execute(tmp_path, 'imported-drop', codegen(SrcFile.from_path(source), debug_locations=False)):
        assert result.stdout == '42\n'


def test_dropped_local_owners_retain_no_storage(tmp_path):
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'fixtures/lifecycle_drop_lifetimes.dewy'
    execute(tmp_path, 'drop-lifetime', codegen(SrcFile.from_path(source), debug_locations=False))


@pytest.mark.parametrize('name', ['lifecycle_drop_aggregate_fields', 'lifecycle_drop_implicit_result', 'lifecycle_drop_nested_fields', 'lifecycle_copy_runtime'])
def test_aggregate_cleanup_and_implicit_results(tmp_path, name):
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / f'fixtures/{name}.dewy'
    execute(tmp_path, name, codegen(SrcFile.from_path(source), debug_locations=False))


@pytest.mark.parametrize('body', [
    'let leaf=TraceHandle[42] let outer=Outer[leaf] return 42',
    'let outer=Outer[TraceHandle[42]] outer.leaf=TraceHandle[1] return 42',
])
def test_nested_owner_transfers_require_ownership_lowering(body):
    source = OWNER + 'Outer=type of [leaf:TraceHandle]\nmain=():>int64=>{'+body+'}'
    with pytest.raises(ReportException, match='lifecycle ownership lowering'):
        codegen(SrcFile(None, source))


def test_nested_implicit_drop_effect_is_in_the_enclosing_contract():
    source = OWNER + 'Outer=type of [leaf:TraceHandle]\nmain=():>int64 & allocates=>{let outer=Outer[TraceHandle[42]] return 42}'
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_nested_implicit_drop_invalidates_facts():
    source = """let changed:int64=0
Leaf=type of [token:int64
$__drop__
release=():>void=>{changed=1}
]
Outer=type of [leaf:Leaf]
main=():>int64=>{changed=0 {let outer=Outer[Leaf[42]]} $assert changed=?0 return 42}
"""
    with pytest.raises(ReportException, match='prove|assert'):
        codegen(SrcFile(None, source))


def test_imported_implicit_drop_fact_error_names_its_own_source(tmp_path):
    module = tmp_path / 'owner.dewy'
    module.write_text("""let changed:int64=0
Handle=type of [token:int64
$__drop__
release=():>void=>{changed=1}
]
probe=():>int64=>{changed=0 {let h=Handle[42]} $assert changed=?0 return 42}
""")
    source = tmp_path / 'main.dewy'
    source.write_text('from p"owner.dewy" import probe\nmain=():>int64=>probe()')
    with pytest.raises(ReportException, match='cannot prove assertion') as error:
        codegen(SrcFile.from_path(source))
    assert str(module) in str(error.value)
