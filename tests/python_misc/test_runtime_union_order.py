"""Runtime tag ordering depends on types, never on executable metadata."""
from dataclasses import replace

from dewy.semantic import ty


class Unrenderable:
    def __repr__(self):
        raise AssertionError('runtime ordering rendered declaration metadata')


def test_order_ignores_defaults_methods_and_proof_provenance():
    opaque = Unrenderable()
    left = ty.ObjectType((ty.ObjectField('x', 'int64', default=opaque),),
                         methods=(ty.MethodSpec('method', opaque),))
    equivalent = ty.ObjectType((ty.ObjectField('x', 'int64', refinement=(
        ty.Proposition('self', '>?', 0, term_id=17),)),))
    right = ty.ObjectType((ty.ObjectField('x', 'string'),))
    assert left == equivalent
    first = ty.runtime_union_members(ty.TypeOr([left, right, 'none']))
    second = ty.runtime_union_members(ty.TypeOr(['none', right, equivalent]))
    assert first == second
    assert first[0] == 'none'


def test_recursive_aliases_use_identity_and_do_not_unfold():
    a = ty.NamedType('Node', 10)
    b = ty.NamedType('Node', 20)
    a.resolve(ty.ObjectType((ty.ObjectField('next', ty.TypeOr([a, 'none'])),)))
    b.resolve(ty.ObjectType((ty.ObjectField('next', ty.TypeOr([b, 'none'])),)))
    first = ty.runtime_union_members(ty.TypeOr([b, a, 'none']))
    second = ty.runtime_union_members(ty.TypeOr([a, 'none', b]))
    assert first == second == ('none', a, b)
    assert ty._runtime_order_key(a) == ty._runtime_order_key(ty.NamedType('Renamed', 10))


def test_shared_type_dag_is_walked_once_and_no_keys_survive_mutation(monkeypatch):
    # Rendering this binary DAG as a tree would visit billions of leaves.
    item = ty.ObjectType((ty.ObjectField('leaf', 'int64'),))
    for _ in range(30):
        item = ty.ObjectType((ty.ObjectField('left', item), ty.ObjectField('right', item)))
    calls = 0
    original = ty.dataclass_fields

    def counted(value):
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(ty, 'dataclass_fields', counted)
    ty._runtime_order_key(item)
    assert calls < 100
    assert ty._runtime_query_cache.get() is None
    mutable = ty.FunctionType([ty.PosOrKwArg('x', 'int64')], [], None, 'bool')
    before = ty._runtime_order_key(mutable)
    mutable.pos_or_kw[0] = replace(mutable.pos_or_kw[0], type='string')
    assert ty._runtime_order_key(mutable) != before
