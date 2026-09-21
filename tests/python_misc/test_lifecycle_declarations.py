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
