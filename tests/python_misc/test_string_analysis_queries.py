"""Pure string-body queries follow function rewrites and compilation lifetimes."""
from dataclasses import replace

from dewy.backend.udewy.lowering_strings import _StringLowering
from dewy.semantic import hir, ty
from dewy.reporting import Span


def test_string_candidates_follow_rewritten_function_bodies():
    loc = Span(0, 0)
    text = ty.StringType()
    first = hir.String(loc, text, 'first')
    second = hir.String(loc, text, 'second')
    declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', 'value', text, first, binding_id=1)
    body = hir.Block(loc, text, [declaration, first], True)
    literal = hir.FunctionLiteral(loc, ty.FunctionType([], [], None, text), [], [], None, text, body)
    def fresh_reader():
        state = _StringLowering()
        state._is_string_valued = lambda type_: isinstance(type_, ty.StringType)
        state.string_candidate_queries = {}
        state.string_body_queries = {}
        return state

    reader = fresh_reader()
    query = _StringLowering._string_local_candidates
    original = query(reader, literal)
    rewritten = replace(literal, body=replace(body, items=[replace(declaration, expr=second), second]))
    assert query(reader, rewritten)[1] == [second]
    assert query(reader, literal)[1] == [first]
    assert original[1] == [first]
    separate = fresh_reader()
    assert query(separate, rewritten)[1] == [second]


def test_string_body_index_excludes_nested_functions_and_preserves_shared_nodes():
    loc = Span(0, 0)
    text = ty.StringType()
    inner_text = hir.String(loc, text, 'inner')
    inner_return = hir.Return(loc, 'never', inner_text)
    signature = ty.FunctionType([], [], None, text)
    inner = hir.FunctionLiteral(loc, signature, [], [], None, text, inner_return)
    shared = hir.String(loc, text, 'outer')
    body = hir.Block(loc, text, [inner, shared, shared], True)
    outer = replace(inner, body=body)
    reader = _StringLowering()
    reader.string_body_queries = {}
    nodes = reader._string_body_nodes(outer)
    assert nodes == (body, shared)
    assert reader._string_body_nodes(outer) is nodes
    assert reader._string_body_nodes(inner) == (inner_return, inner_text)
    rewritten = replace(outer, body=shared)
    assert reader._string_body_nodes(rewritten) == (shared,)
