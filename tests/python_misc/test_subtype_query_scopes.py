"""Subtype reuse belongs to a stable decision, not a checker session."""
import weakref

from dewy.semantic import ty


def test_compound_subtyping_reuses_results_and_keeps_identity_inputs_alive(monkeypatch):
    system = ty.TypeSystem()
    actual = ty.ArrayType(ty.TypeAnd(['int64', 'any']))
    required = ty.ArrayType('int64')
    original = system._compound_subtype
    calls = []
    def counted(s, t):
        calls.append((id(s), id(t)))
        return original(s, t)
    monkeypatch.setattr(system, '_compound_subtype', counted)
    with ty.runtime_query_scope():
        assert system.is_subtype(actual, required)
        before = len(calls)
        assert system.is_subtype(actual, required)
        assert len(calls) == before
        reference = weakref.ref(actual)
        del actual
        assert reference() is not None
    assert reference() is None
    assert ty._runtime_query_cache.get() is None


def test_nominal_graph_changes_invalidate_only_that_systems_relations():
    first, second = ty.TypeSystem(), ty.TypeSystem()
    for system in (first, second):
        system.add_type('textual')
    actual = ty.StringType()
    with ty.runtime_query_scope():
        assert not first.is_subtype(actual, 'textual')
        assert not second.is_subtype(actual, 'textual')
        first.add_type_link('string', 'textual')
        assert first.is_subtype(actual, 'textual')
        assert not second.is_subtype(actual, 'textual')


def test_dispatch_observes_alias_changes_between_pure_decisions():
    system = ty.TypeSystem()
    methods = [ty.FunctionType([ty.PosOrKwArg('value', ty.ArrayType(element))], [], None, element)
               for element in ('int64', 'string')]
    element = ty.TypeAnd(['int64', 'any'])
    argument = ty.ArrayType(element)
    assert system.match_best_function(methods, [argument]).method_index == 0
    assert ty._runtime_query_cache.get() is None
    element.items[:] = ['string', 'any']
    assert system.match_best_function(methods, [argument]).method_index == 1
    assert ty._runtime_query_cache.get() is None


def test_representation_registration_is_observed_after_query_scope():
    system = ty.TypeSystem()
    target = ty.ObjectType((ty.ObjectField('word', 'int64'),))
    value = ty.IntegerLiteralType(1)
    with ty.runtime_query_scope():
        assert not system.is_subtype(value, target)
    system.rational_object = target
    with ty.runtime_query_scope():
        assert system.is_subtype(value, target)
    system.rational_object = None
    assert not system.is_subtype(value, target)
