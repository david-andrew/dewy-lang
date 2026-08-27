"""Calling an object type constructs it: the field list is the constructor's signature."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError

SPAN = 'let Span:type = [start:int64 stop:int64 = start label:string = "span"]\n'


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, '$no_prelude = true\n' + source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_constructor_calls_become_object_literals_with_defaults() -> None:
    declared = _declared(SPAN + 'let a = Span(1 9)\nlet b = Span(stop=5 start=2 label="b")\nlet c = Span(7)\n')
    for name in ('a', 'b', 'c'):
        literal = declared[name].expr
        assert isinstance(literal, hir.ObjectLiteral)
        assert [f.name for f in literal.fields] == ['start', 'stop', 'label']
    c_fields = {f.name: f.value for f in declared['c'].expr.fields}
    assert isinstance(c_fields['stop'], hir.ExpressedIdentifier) and c_fields['stop'].name == 'start'  # the default `= start`
    label = c_fields['label']
    while isinstance(label, hir.RepresentationCast):
        label = label.expr
    assert isinstance(label, hir.String) and label.content == 'span'


def test_constructor_diagnostics() -> None:
    cases = [
        ('Span()', UserError, 'missing constructor argument `start`'),
        ('Span(1 width=3)', UserError, 'has no field `width`'),
        ('Span(1 2 "x" 4)', UserError, 'too many constructor arguments'),
        ('Span(1 start=2)', UserError, 'is given twice'),
        ('Span("a")', TypeCheckError, 'type mismatch'),
    ]
    for call, error, message in cases:
        with pytest.raises(error, match=message):
            _declared(SPAN + f'let s = {call}\n')


def test_constructed_values_lower_like_literals() -> None:
    emitted = codegen(SrcFile(None, SPAN + 'let main = ():>int64 => { let s = Span(1 9)  let xs:array<Span> = []  xs.push(Span(2))  return s.stop - s.start + xs.length }\n'))
    assert 'main' in emitted
