"""The module policy is enforced by lowering, including direct API use."""
import pytest

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lower import lower_for_udewy
from dewy.reporting import ReportException, SrcFile
from dewy.semantic.check import typecheck_and_resolve
from test_scalar_projection import execute

SOURCE = """
Box:type=[text:string number:int64]
read=(values:array<Box>):>int64=>{
    if values.length =? 0 return 0
    let saved=values[0]
    values[0].number=99
    return saved.number
}
main=():>int64=>read([Box['hello' 42]])
"""


def test_direct_codegen_rejects_implicit_runtime_sized_copy():
    with pytest.raises(ReportException, match='unproven copy') as error:
        codegen(SrcFile(None, '$explicit_copies\n'+SOURCE))
    assert 'bound to `saved`' in str(error.value)
    assert '`.copy()`' in str(error.value)


def test_direct_checked_hir_lowering_retains_policy():
    source = SrcFile(None, '$explicit_copies\n'+SOURCE)
    checked = typecheck_and_resolve(source, include_prelude=True)
    with pytest.raises(ReportException, match='unproven copy'):
        lower_for_udewy(checked, source)


def test_explicit_remedy(tmp_path):
    body = SOURCE.replace('read=(values:array<Box>):>int64=>{', 'read=(source:array<Box>):>int64=>{let values=source.copy()')
    source = SrcFile(None, '$explicit_copies\n'+body.replace('let saved=values[0]', 'let saved=values[0].copy()'))
    execute(tmp_path, 'explicit-policy', codegen(source, debug_locations=False))


def test_required_view_and_last_use_move(tmp_path):
    source = SrcFile(None, """$explicit_copies
Box:type=[text:string number:int64]
main=():>int64=>{
    let box=Box['hello' 42]
    const view=@box
    return view.number
}
""")
    execute(tmp_path, 'view-policy', codegen(source, debug_locations=False))


@pytest.mark.parametrize('directive', ['', '$explicit_copies=false'])
def test_policy_disabled(directive):
    codegen(SrcFile(None, directive+'\n'+SOURCE))


@pytest.mark.parametrize('directive,diagnostic', [
    ('$explicit_copies=1', 'must be a boolean literal'),
    ('$explicit_copies\n$explicit_copies=false', 'duplicate'),
])
def test_policy_syntax(directive, diagnostic):
    with pytest.raises(ReportException, match=diagnostic):
        codegen(SrcFile(None, directive+'\nmain=():>int64=>42'))


def test_imported_policy_keeps_definition_source(tmp_path):
    dependency = tmp_path / 'strict.dewy'
    dependency.write_text('$explicit_copies\n'+SOURCE.replace('main=', 'invoke='))
    entry = tmp_path / 'main.dewy'
    entry.write_text('import p"strict.dewy" as strict\nmain=():>int64=>strict.invoke()')
    with pytest.raises(ReportException, match='unproven copy') as error:
        codegen(SrcFile.from_path(entry))
    assert 'strict.dewy' in str(error.value)


def test_entry_policy_does_not_apply_to_unmarked_dependency(tmp_path):
    dependency = tmp_path / 'ordinary.dewy'
    dependency.write_text(SOURCE.replace('main=', 'invoke='))
    entry = tmp_path / 'main.dewy'
    entry.write_text('$explicit_copies\nimport p"ordinary.dewy" as ordinary\nmain=():>int64=>ordinary.invoke()')
    codegen(SrcFile.from_path(entry))


@pytest.mark.parametrize('call', ['change(values)', 'change(values=values)'])
def test_implicit_array_argument_copy_is_reported_and_enforced(call):
    source = SrcFile(None, 'change=(values:array<int64>):>void=>{values.push(99)} '
                     'main=():>int64=>{let values:array<int64>=[42] '+call+'; return values[0]}')
    from dewy.backend.udewy import lower
    codegen(source)
    assert any(note.kind == 'array' and note.site == 'passed to a call'
               for note in lower.last_copy_notes)
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source.body))


def test_implicit_array_assignment_is_reported_and_enforced():
    source = SrcFile(None, 'replace_values=(@target:array<int64> source:array<int64>):>void=>{target=source} '
                     'main=():>int64=>{let target:array<int64>=[] replace_values(@target [42]) '
                     'if target.length =? 0 return 1 return target[0]}')
    from dewy.backend.udewy import lower
    codegen(source)
    assert any(note.kind == 'array' and 'assigned to' in note.site
               for note in lower.last_copy_notes)
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, '$explicit_copies\n'+source.body))
