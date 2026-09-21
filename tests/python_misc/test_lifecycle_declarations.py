"""Approved lifecycle member shape, independent of runtime ownership lowering."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic import check, hir


def checked(source):
    return check.typecheck_and_resolve(SrcFile(None, '$no_prelude=true\n' + source))


def owner(body, *, nominal=True):
    return 'Handle:type=' + ('type of ' if nominal else '') + '[token:int64\n' + body + '\n]\n'


def test_hooks_have_a_place_receiver_even_without_member_reads():
    root = checked(owner('''$__drop__
release=():>void=>{}
$__copy__
duplicate=():>Handle=>Handle[token]
$__move__
transfer=():>Handle=>Handle[token]'''))
    functions = [item.expr for item in root.items if isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral)]
    assert len(functions) == 3
    assert [fn.lifecycle for fn in functions] == ['drop', 'copy', 'move']
    assert all(len(fn.pos_or_kw_args) == 1 and fn.pos_or_kw_args[0].place for fn in functions)
    declaration = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'Handle')
    assert [m.lifecycle for m in declaration.expr.value.methods] == ['drop', 'copy', 'move']


@pytest.mark.parametrize('body, message', [
    ('$__drop__', 'must mark a method'),
    ('$__drop__\nother:int64', 'must mark a method'),
    ('$__drop__\n$__copy__\nf=():>void=>{}', 'must mark a method'),
    ('$__drop__\na=():>void=>{}\n$__drop__\nb=():>void=>{}', 'duplicate lifecycle'),
    ('$__drop__\nf=(x:int64):>void=>{}', 'no explicit parameters'),
    ('$__drop__\nf=(x:int64=0):>void=>{}', 'no explicit parameters'),
    ('$__drop__\nf=<T>(x:T):>void=>{}', 'generic parameters'),
    ('$__drop__\nf=():>int64=>42', 'invalid lifecycle hook result'),
    ('$__copy__\nf=():>void=>{}', 'invalid lifecycle hook result'),
    ('$__move__\nf=():>int64=>42', 'invalid lifecycle hook result'),
    ('$__copy__\nf=():>Handle=>{token=0 return Handle[token]}', 'read-only receiver'),
    ('$__copy__\nf=():>Handle=>{touch(@token) return Handle[token]}', 'read-only receiver'),
    ('$__drop__\nf=():>void=>{}\nf &= (x:int64):>void=>{}', 'cannot be overloaded'),
    ('$__drop__\nf=():>void=>{}\ng=():>void=>f()', 'compiler-only'),
])
def test_invalid_hook_declarations(body, message):
    with pytest.raises(ReportException, match=message):
        checked('touch=(@x:int64):>void=>{x=1}\n' + owner(body))


@pytest.mark.parametrize('use', ['h.release()', 'let fn=h.release', 'Handle.release()', 'let fn=Handle.release'])
def test_hooks_are_not_source_callables(use):
    with pytest.raises(ReportException, match='compiler-only'):
        checked(owner('$__drop__\nrelease=():>void=>{}') + 'main=():>void=>{let h=Handle[42]\n' + use + '\n}')


def test_structural_owner_is_rejected():
    with pytest.raises(ReportException, match='nominal type'):
        checked(owner('$__drop__\nrelease=():>void=>{}', nominal=False))


def test_standalone_marker_is_not_a_scope_label():
    with pytest.raises(ReportException, match='nominal type member'):
        checked('$__drop__\nf=():>void=>{}')


def test_inferred_drop_result_is_void():
    checked(owner('$__drop__\nrelease=()=>{}'))


def test_result_must_be_same_nominal_identity():
    with pytest.raises(ReportException, match='invalid lifecycle hook result'):
        checked('Other=type of [token:int64]\n' + owner('$__copy__\nf=():>Other=>Other[token]'))


def test_hook_effect_contract_is_checked_normally():
    source = owner('$__drop__\nrelease=():>void & no_effects=>{touch(@outside)}')
    with pytest.raises(ReportException, match='effect contract'):
        checked('let outside:int64=0\ntouch=(@x:int64):>void=>{x=1}\n' + source)


def test_ownership_lowering_does_not_silently_ignore_hooks():
    with pytest.raises(ReportException, match='lifecycle ownership lowering'):
        codegen(SrcFile(None, owner('$__drop__\nrelease=():>void=>{}') + 'main=():>int64=>{let h=Handle[42] return h.token}'))


def test_observable_hook_effects_are_allowed_without_a_pure_contract():
    source = owner('$__drop__\nrelease=():>void=>printl("release")')
    check.typecheck_and_resolve(SrcFile(None, source), include_prelude=True)


def test_inherited_hooks_are_explicitly_pending():
    with pytest.raises(ReportException, match='inherited lifecycle hooks'):
        checked(owner('$__drop__\nrelease=():>void=>{}') + 'DerivedHandle:type=type of Handle & [extra:int64]')


def test_nested_function_cannot_write_through_copy_receiver():
    body = '$__copy__\nf=():>Handle=>{let write=():>void=>{token=1} write() return Handle[token]}'
    with pytest.raises(ReportException, match='read-only receiver'):
        checked(owner(body))


@pytest.mark.parametrize('name', ['duplicate', 'copy'])
@pytest.mark.parametrize('call', ['h.copy()', 'h.copy'])
def test_custom_copy_is_a_checked_call_on_a_const_receiver(name, call):
    root = checked(owner(f'$__copy__\n{name}=():>Handle=>Handle[token]') + f'f=():>Handle=>{{const h=Handle[42] return {call}}}')
    declaration = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'f')
    calls = [item for item in hir.walk(declaration.expr.body) if isinstance(item, hir.FunctionCall)]
    hook_call = next(item for item in calls if isinstance(item.func, hir.ExpressedIdentifier) and item.func.name.endswith('$lifecycle'))
    assert len(hook_call.pos_args) == 1 and isinstance(hook_call.pos_args[0], hir.Place)
    assert not any(isinstance(item, hir.CopyValue) for item in hir.walk(declaration.expr.body))


def test_explicit_copy_of_move_only_value_is_rejected():
    with pytest.raises(ReportException, match='cannot copy a move-only value'):
        checked(owner('$__drop__\nrelease=():>void=>{}') + 'f=():>Handle=>{let h=Handle[42] return h.copy()}')


def test_custom_copy_cannot_hide_external_effects_from_caller():
    source = ('let changed:int64=0\n' + owner('$__copy__\nduplicate=():>Handle=>{changed=1 return Handle[token]}')
              + 'f=():>Handle & no mutates=>{let h=Handle[42] return h.copy()}')
    with pytest.raises(ReportException, match='effect contract'):
        checked(source)


def test_custom_copy_does_not_inherit_source_field_facts():
    source = (owner('$__copy__\nduplicate=():>Handle=>Handle[0]')
              + 'f=():>void=>{let h=Handle[42] let c=h.copy() $assert c.token =? 42}')
    with pytest.raises(ReportException, match='assert'):
        checked(source)


def test_internal_receiver_abi_does_not_introduce_external_effects():
    checked(owner('$__drop__\nrelease=():>void & no_effects=>{if token >? 0 {token=0}}'))
    checked(owner('$__copy__\nduplicate=():>Handle & no reads=>Handle[token]'))


def test_hook_cannot_escape_through_an_inherited_function_slot():
    source = '''Protocol=type of [release:():>void]
Handle=type of Protocol & [
    $__drop__
    release=():>void=>{}
]
'''
    with pytest.raises(ReportException, match='cannot implement a callable field'):
        checked(source)
