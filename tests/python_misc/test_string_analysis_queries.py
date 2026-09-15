"""Pure string-body queries follow function rewrites and compilation lifetimes."""
from dataclasses import replace
from types import SimpleNamespace

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
    reader = SimpleNamespace(
        _is_string_valued=lambda type_: isinstance(type_, ty.StringType),
        string_candidate_queries={},
    )
    query = _StringLowering._string_local_candidates
    original = query(reader, literal)
    rewritten = replace(literal, body=replace(body, items=[replace(declaration, expr=second), second]))
    assert query(reader, rewritten)[1] == [second]
    assert query(reader, literal)[1] == [first]
    assert original[1] == [first]
    separate = SimpleNamespace(_is_string_valued=reader._is_string_valued, string_candidate_queries={})
    assert query(separate, rewritten)[1] == [second]
