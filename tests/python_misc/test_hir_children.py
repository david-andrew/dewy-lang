"""Structural HIR walks include syntax containers and leave metadata opaque."""
from dataclasses import dataclass

import pytest

from dewy.reporting import Span, SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.analyze.bounds import _assigned_binding_ids
from dewy.semantic.errors import UserError

LOC = Span(0, 0)


def integer(value):
    return hir.Integer(LOC, 'int64', '0d', value)


def test_children_include_bound_parameters_fields_and_keyword_arguments():
    default, body, argument = integer(1), integer(2), integer(3)
    param = hir.BoundParam('value', 'int64', default)
    function = hir.FunctionLiteral(LOC, ty.FunctionType([], [], None, 'int64'),
                                   [param], [], None, 'int64', body)
    call = hir.FunctionCall(LOC, 'int64', function, [], {'value': argument})
    root = hir.ObjectLiteral(LOC, ty.ObjectType([]), [hir.ObjectField(LOC, 'result', call)])
    assert list(hir.walk(root)) == [root, call, function, default, body, argument]
    assert hir.child_fields(hir.Integer) == ()
    assert hir.child_fields(hir.FunctionLiteral) == (
        'pos_or_kw_args', 'kw_only_args', 'rest_args', 'body')


@dataclass
class NestedSyntax(hir.AST):
    values: dict[str, list[hir.AST | None]]
    metadata: object


def test_nested_syntax_sequences_preserve_order_and_metadata_stays_opaque():
    first, second, metadata = integer(1), integer(2), integer(3)
    root = NestedSyntax(LOC, 'void', {'a': [first, None], 'b': [second]}, metadata)
    assert list(hir.children(root)) == [first, second]


def test_walk_preserves_shared_occurrences_and_handles_deep_syntax():
    shared = integer(1)
    root = hir.Block(LOC, 'void', [shared, shared], False)
    assert [id(node) for node in hir.walk(root)] == [id(root), id(shared), id(shared)]
    for _ in range(2000):
        root = hir.Suppress(LOC, 'void', root)
    nodes = list(hir.walk(root))
    assert len(nodes) == 2003
    assert nodes[-1] is nodes[-2] is shared


def test_planned_children_match_generic_fields_on_checked_syntax():
    root = check.typecheck_and_resolve(SrcFile(None, '''
Box:type=[value:int64]
let choose=(x:int64=3):>Box=>[value=if x >? 0 x else -x]
let main=()=>{let xs=[1 2]\nloop x in xs {let box=choose(x=x)\n"{box.value}";}}
'''))
    for node in hir.walk(root):
        reference = [child for name in hir.child_fields(type(node))
                     for child in hir._child_values(getattr(node, name))]
        assert [id(child) for child in hir.children(node)] == [id(child) for child in reference]


def test_assignment_discovery_reaches_fields_and_keyword_arguments():
    target = hir.ExpressedIdentifier(LOC, 'int64', 'changed', binding_id=17)
    assignment = hir.Assign(LOC, 'void', target, '=', integer(-1))
    function = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'void'), 'f')
    call = hir.FunctionCall(LOC, 'void', function, [], {'value': assignment})
    root = hir.ObjectLiteral(LOC, ty.ObjectType([]), [hir.ObjectField(LOC, 'field', call)])
    assert _assigned_binding_ids(root) == {17}


def test_mutation_in_an_object_initializer_invalidates_global_bounds():
    source = SrcFile(None, '''
let n:int64=1
change=()=>{let box=[value={n=-1\n0}]}
positive=()=>{$assert n >? 0}
''')
    with pytest.raises(UserError, match='cannot prove assertion'):
        check.typecheck_and_resolve(source)
