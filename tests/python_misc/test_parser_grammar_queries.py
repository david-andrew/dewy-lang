"""Grammar lookup reuse must preserve ambiguities, positions and subclasses."""
import pickle

import pytest

from dewy.parser import p0, t0, t1, t2
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


def test_token_membership_retains_abstract_and_inherited_contracts():
    class AbstractToken(t1.Token):
        pass

    with pytest.raises(TypeError, match='abstract'):
        AbstractToken(Span(0, 0))
    with pytest.raises(TypeError, match='abstract'):
        t0.Token()

    class ExtendedIdentifier(t1.Identifier):
        pass

    node = ExtendedIdentifier(Span(0, 1), 'x')
    assert isinstance(node, t1.Identifier)
    assert isinstance(node, t1.Token)
    assert issubclass(ExtendedIdentifier, t1.Token)
    assert not isinstance(node, t1.Operator)
    assert not issubclass(ExtendedIdentifier, t1.Operator)
    with pytest.raises(TypeError, match='must inherit'):
        t1.Token.register(str)


def test_quantum_precedence_uses_current_alternatives():
    node = t2.QJuxtapose(Span(0, 0))
    before = p0.get_precedence(node)
    assert isinstance(before, p0.qint)
    node.options = [t2.CallJuxtapose(node.loc), t2.IndexJuxtapose(node.loc)]
    assert p0.get_precedence(node) == p0.get_precedence(node.options[0])


def test_recursion_dispatch_matches_registry_and_inherits_container_handlers(monkeypatch):
    sources = [
        "f'a{if x 1 else 2}b'",
        'loop x in 0..3 {if x >? 1 {f(x)} else g(x)}',
        '$runtime_assert (x >? 0), "value {x}"',
        'import parser as p\nlet f=(x:int64):>int64=>x+1',
    ]
    expected = [pickle.dumps(p0.parse(SrcFile(None, source))) for source in sources]
    monkeypatch.setattr(t2, 'recurse_into', t2._recurse_dispatch)
    assert [pickle.dumps(p0.parse(SrcFile(None, source))) for source in sources] == expected

    class ExtendedBlock(t1.Block):
        pass
    assert t2._recurse_handler(ExtendedBlock) is t2._recurse_handler(t1.Block)
    leaf = t1.Identifier(Span(0, 1), 'x')
    calls = []
    t2._recurse_handler(type(leaf))(leaf, calls.append)
    assert not calls


@pytest.mark.parametrize('source', [
    'f(,,)\n[type of A & B] += [. + (x not <? y)]',
    'let f=(x:int64):>int64=>if not x =? 1 {x*2} else 3',
    "let text=\"result {f(a += b)}\"",
    'let partials=[(<? 3) (.length) (* 2) (+) (.+=)]',
    'let f=<T of A & B>(value:T):>T=>value',
])
def test_context_inventory_preserves_recursive_phase_order(source, monkeypatch):
    current = pickle.dumps(p0.parse(SrcFile(None, source)))
    def recursive_pipeline(tokens, *, ctx):
        t2.remove_whitespace(tokens)
        t2.insert_juxtapose(tokens, ctx=ctx)
        for rewrite in (t2.insert_comma_voids, t2.make_type_of_operators,
                        t2.make_inverted_comparisons, t2.make_broadcast_operators,
                        t2.make_combined_assignment_operators, t2.make_partial_operators,
                        t2.make_op_functions, t2.make_placeholders):
            rewrite(tokens)
        t2.bundle_keyword_exprs(tokens, ctx=ctx)
        t2.make_chains(tokens, ctx=ctx)
    monkeypatch.setattr(t2, 'postok_inner', recursive_pipeline)
    assert pickle.dumps(p0.parse(SrcFile(None, source))) == current


@pytest.mark.parametrize('source', [
    'a + b', 'a - b', 'a * b', 'a ^ b', '-a', '+a', 'not a', '@a',
    'a or_throw', 'a as T', 'a transmute T', 'a[b]', 'f(x)', '2x',
    'a + b * c - d', 'a^b^c', 'f(x)^2 + 2x^2', 'not a =? b',
    'a,b', '0..3', '0,2..8', 'a;b', ';a', 'a;',
    'let f=(x:int64=1):>int64=>x+1', 'let values=[a b c]',
    '(+)', '(* 2)', '(.length)', 'a not <? b', 'a .+ b',
])
def test_isolated_reductions_match_general_shunting(source, monkeypatch):
    file = SrcFile(None, source)
    actual = pickle.dumps(p0.parse(file))
    monkeypatch.setattr(p0, '_single_reduction', lambda items, ctx: None)
    assert pickle.dumps(p0.parse(file)) == actual


@pytest.mark.parametrize('source', ['a..b..c', 'a:b:c', 'let a = 0..1..2'])
def test_isolated_reductions_keep_nonassociative_errors(source, monkeypatch):
    file = SrcFile(None, source)
    with pytest.raises(Exception) as actual:
        p0.parse(file)
    monkeypatch.setattr(p0, '_single_reduction', lambda items, ctx: None)
    with pytest.raises(type(actual.value)) as expected:
        p0.parse(file)
    assert str(expected.value) == str(actual.value)
