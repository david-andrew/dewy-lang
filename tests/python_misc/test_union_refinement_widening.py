"""Adding union alternatives retains existing member contracts, never invents them."""

from types import SimpleNamespace

import pytest

from dewy.reporting import Span, SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError


def test_refined_union_member_survives_optional_field_copy():
    check.typecheck_and_resolve(SrcFile(None, '''
Alias:type = const [name:string]
Value:type = addr | Alias
Box:type = const [value:Value?]
copy = (input:Box):>Box => {
    if input.value isnt? none return Box[input.value]
    return Box[none]
}
'''))


@pytest.mark.parametrize('source', ['int64', 'int64<i => i >=? 0>'])
def test_widening_union_does_not_supply_a_stronger_member_contract(source):
    with pytest.raises(UserError, match='cannot prove refinement'):
        check.typecheck_and_resolve(SrcFile(None, f'''
Alias:type = const [name:string]
copy = (input:{source} | Alias):>int64<i => i >? 0> | Alias | none => input
'''))


@pytest.mark.parametrize('same_binding', [True, False])
def test_union_contract_copies_keep_resolved_term_identity(same_binding):
    src = ty.Proposition('self', '<=?', 0, term='src', term_id=7)
    dst = ty.Proposition('self', '<=?', 0, term='src', term_id=7 if same_binding else 8)
    record = ty.ObjectType((ty.ObjectField('name', 'string'),))
    source = ty.union(ty.RefinedType('int64', (src,)), record)
    target = ty.union(ty.RefinedType('int64', (dst,)), record, 'none')
    node = hir.ExpressedIdentifier(Span(0, 0), source, 'value', binding_id=9)
    context = SimpleNamespace(srcfile=SrcFile(None, ''), type_system=ty.TypeSystem(), binding_scopes={})
    result = check.check_against(node, target, ctx=context)
    if same_binding:
        assert result is node
    else:
        assert isinstance(result, hir.Obligation)
        assert result.refined.propositions[0].term_id == 8
