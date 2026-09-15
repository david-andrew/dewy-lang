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
