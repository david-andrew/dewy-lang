"""Methods declared in object types (hidden `Type__method(receiver …)` functions) and `&=` constructor overloads."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError

SPAN = (
    'let Span:type = [\n'
    '    start:int64\n'
    '    stop:int64 = start\n'
    '    width = () => stop - start\n'
    '    grow = (by:int64) => { stop += by }\n'
    '    shifted = (by:int64):>Span => Span(start + by stop + by)\n'
    ']\n'
)


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_methods_are_hoisted_functions_taking_self() -> None:
    declared = _declared(SPAN + 'let main = ():>int64 => { let s = Span(1 3)  s.grow(2)  return s.width + s.shifted(1).stop }\n')
    assert isinstance(declared['Span__width'].expr, hir.FunctionLiteral)
    width = declared['Span__width'].expr.type
    assert isinstance(width, ty.FunctionType) and [p.name for p in width.pos_or_kw] == ['__dewy_receiver'] and not width.pos_or_kw[0].place
    grow = declared['Span__grow'].expr.type
    assert isinstance(grow, ty.FunctionType) and grow.pos_or_kw[0].place  # `stop += by` mutates a field
    body = declared['main'].expr.body
    calls = [node for node in _walk(body) if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ExpressedIdentifier) and node.func.name.startswith('Span__')]
    assert {call.func.name for call in calls} == {'Span__grow', 'Span__width', 'Span__shifted'}
    grow_call = next(call for call in calls if call.func.name == 'Span__grow')
    assert isinstance(grow_call.pos_args[0], hir.Place)  # the receiver is passed as a place


def _walk(node):
    from dataclasses import fields, is_dataclass
    yield node
    if is_dataclass(node):
        for f in fields(node):
            value = getattr(node, f.name)
            if isinstance(value, hir.AST):
                yield from _walk(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, hir.AST):
                        yield from _walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, hir.AST):
                        yield from _walk(item)


def test_method_diagnostics() -> None:
    with pytest.raises(UserError, match='needs a place'):
        _declared(SPAN + 'let main = ():>int64 => { Span(1 3).grow(2)  return 0 }\n')
    with pytest.raises(TypeCheckError, match='must be called'):
        _declared(SPAN + 'let main = ():>int64 => { let s = Span(1 3)  let g = s.grow  return 0 }\n')
    # `self` is not a name the language knows: a parameter may be called that, and a bare `self` in a body is undefined
    _declared('let T:type = [x:int64 f = (self:int64) => self + x]\nlet main = ():>int64 => 0\n')
    with pytest.raises(UserError, match='undefined identifier `self`'):
        _declared('let T:type = [x:int64 f = () => self]\nlet main = ():>int64 => 0\n')
    with pytest.raises(UserError, match='duplicate object member'):
        _declared('let T:type = [x:int64 x = () => 1]\nlet main = ():>int64 => 0\n')
    with pytest.raises(NotImplementedYet, match='inside a function'):
        _declared('let main = ():>int64 => { let T:type = [x:int64 f = () => x]  return 0 }\n')


def test_constructor_overloads_dispatch_by_signature() -> None:
    source = (
        SPAN
        + 'Span &= (text:string):>Span => Span(0 text.length)\n'
        + 'Span &= (center:int64 radius:int64 wide:bool):>Span => Span(center - radius center + radius)\n'
        + 'let a = Span(1 9)\nlet b = Span("seven..")\nlet c = Span(10 3 false)\n'
    )
    declared = _declared(source)
    assert isinstance(declared['a'].expr, hir.ObjectLiteral)  # the field-wise constructor
    assert isinstance(declared['b'].expr, hir.FunctionCall) and declared['b'].expr.func.name == 'Span__new_1'
    assert isinstance(declared['c'].expr, hir.FunctionCall) and declared['c'].expr.func.name == 'Span__new_2'
    with pytest.raises(UserError, match='a constructor overload must be a function literal'):
        _declared(SPAN + 'Span &= 5\n')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared(source + 'let d = Span(true)\n')  # no overload takes a bool: the field-wise errors apply


def test_methods_lower_and_run_through_codegen() -> None:
    emitted = codegen(SrcFile(None, SPAN + 'let main = ():>int64 => { let s = Span(1 3)  s.grow(2)  return s.width }\n'))
    assert 'Span__grow' in emitted and 'Span__width' in emitted
