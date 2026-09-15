"""Grammar lookup reuse must preserve ambiguities, positions and subclasses."""
import pickle

import pytest

from dewy.parser import p0, t1, t2
from dewy.reporting import Span, SrcFile


@pytest.mark.parametrize('source', [
    'f(x)^2 + 2x^2',
    'a[b] + (a)b',
    'a + b * -c',
    'let f=(x:int64):>int64=>if x >? 0 x else -x',
    'let x:int64?=none\nx or_throw',
    'not a =? b and c not =? d',
    'type of Token & [text:string]',
    'let f=<T of A & B>(x:T):>T=>x',
    'loop x in 0..3 {if x=?1 continue\ny+=x}',
    '(<? 3)\n(.length)\n(* 2)\n(+)',
])
def test_cached_grammar_queries_preserve_reference_trees(source, monkeypatch):
    file = SrcFile(None, source)
    cached = pickle.dumps(p0.parse(file))
    monkeypatch.setattr(t2, 'is_operator', lambda token: isinstance(token, t2.Operator))
    monkeypatch.setattr(p0, '_combined_precedence', p0._combined_precedence.__wrapped__)
    monkeypatch.setattr(p0, '_combined_bind_power', p0._combined_bind_power.__wrapped__)
    assert pickle.dumps(p0.parse(file)) == cached


def test_operator_classification_honors_inherited_tokens():
    class ExtendedOperator(t1.Operator):
        pass

    class ExtendedCall(t2.CallJuxtapose):
        pass

    assert t2.is_operator(ExtendedOperator(Span(0, 1), '+'))
    assert t2.is_operator(ExtendedCall(Span(1, 1)))
    assert not t2.is_operator(t1.Identifier(Span(0, 1), 'x'))
    assert not t2.is_operator(None)


def test_quantum_precedence_uses_current_alternatives():
    node = t2.QJuxtapose(Span(0, 0))
    before = p0.get_precedence(node)
    assert isinstance(before, p0.qint)
    node.options = [t2.CallJuxtapose(node.loc), t2.IndexJuxtapose(node.loc)]
    assert p0.get_precedence(node) == p0.get_precedence(node.options[0])
