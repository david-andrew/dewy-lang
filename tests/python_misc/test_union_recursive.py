"""Recursive types: self-reference as a union member, narrowing on member routes."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.semantic.hir_display import type_to_dewy

NODE = 'let Node:type = [value:int64 next:Node|undefined]\n'


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_recursive_alias_unfolds_to_an_object_with_a_reference_member() -> None:
    declared = _declared(NODE)
    value = declared['Node'].expr.value
    assert isinstance(value, ty.ObjectType)
    next_type = value.field('next').type
    assert isinstance(next_type, ty.TypeOr)
    reference = next((item for item in next_type.items if isinstance(item, ty.NamedType)), None)
    assert reference is not None and reference.name == 'Node' and reference.target is value
    assert type_to_dewy(value) == '[value:int64 next:Node | undefined]'


def test_recursion_without_a_union_is_rejected() -> None:
    with pytest.raises(UserError, match='refers to itself without a union'):
        _declared('let Node:type = [value:int64 next:Node]\n')


def test_recursion_without_a_base_case_is_rejected() -> None:
    with pytest.raises(UserError, match='has no base case'):
        _declared('let Node:type = [next:Node|Node]\n')


def test_non_object_recursion_is_rejected() -> None:
    with pytest.raises(UserError, match='must be an object type'):
        _declared('let Chain:type = <(next:Chain|undefined):>int64>\n')


def test_member_routes_narrow_and_forget_on_assignment() -> None:
    source = NODE + '''
let peek = (node:Node):>int64 => {
    if node.next is? Node { return node.next.value }
    return 0
}
'''
    _declared(source)  # `node.next.value` reads the narrowed route
    # unnarrowed, `node.next.value` is safe navigation: `int64 | undefined`,
    # which does not fit the `int64` result
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared(NODE + 'let peek = (node:Node):>int64 => node.next.value\n')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared(NODE + '''
let peek = (node:Node other:Node):>int64 => {
    if node.next is? Node {
        node.next = undefined
        return node.next.value
    }
    return 0
}
''')


def test_every_spelling_of_the_union_shares_one_member_order() -> None:
    declared = _declared(NODE + 'let f = (a:Node|undefined):>Node|undefined => a\n')
    signature = declared['f'].expr.type
    assert isinstance(signature, ty.FunctionType)
    param_members = ty.runtime_union_members(ty.optional(signature.pos_or_kw[0].type)) or ('undefined', ty.optional_payload(signature.pos_or_kw[0].type))
    node_value = declared['Node'].expr.value
    field_members = ('undefined', ty.optional_payload(node_value.field('next').type))
    assert param_members == field_members
    assert isinstance(field_members[1], ty.NamedType)


def test_recursive_members_lower_to_handles_with_a_copy_function() -> None:
    emitted = codegen(SrcFile(None, NODE + '''
let main = ():>int64 => {
    let list:Node|undefined = undefined
    list = [value=1 next=list]
    let copy:Node|undefined = list
    if copy is? Node { return copy.value }
    return 0
}
'''))
    assert '__dewy_copy_Node' in emitted
    assert '_arena_alloc' in emitted


def test_three_member_union_with_undefined_crosses_calls() -> None:
    emitted = codegen(SrcFile(None, NODE + '''
let pick = (v:Node|int64|undefined):>int64 => {
    if v is? Node { return v.value }
    else if v is? int64 { return v }
    return 0
}
let main = ():>int64 => pick([value=5 next=undefined]) + pick(2) + pick(undefined)
'''))
    assert 'let pick' in emitted
