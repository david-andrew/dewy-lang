"""Lazy proof routes must never overwrite declarations or change their ids."""

import pickle

from dewy.reporting import Span
from dewy.semantic.bindings import BindingRegistry


LOC = Span(0, 0)


def test_allocators_stay_disjoint_beyond_old_route_boundary():
    registry = BindingRegistry()
    owner = registry.allocate(object(), 'owner', 'value', LOC)
    # Advance the cursor without constructing half a million unrelated nodes.
    registry.next_id = 2**19 - 1
    declarations = [registry.allocate(object(), 'value', 'value', LOC) for _ in range(3)]
    routes = [registry.route_id(owner.id, (name,), 'int64', LOC) for name in ('a', 'b')]
    assert len({owner.id, *routes, *(binding.id for binding in declarations)}) == 6
    assert all(registry.by_id[binding.id] is binding for binding in declarations)
    assert all(registry.by_id[route].route_root == owner.id for route in routes)
    restored = pickle.loads(pickle.dumps(registry))
    assert restored.route_id(owner.id, ('a',), 'int64', LOC) == routes[0]
    assert restored.allocate_param('argument', 'int64', LOC).id not in registry.by_id
    assert restored.route_id(owner.id, ('c',), 'int64', LOC) not in registry.by_id


def test_validation_routes_do_not_shift_declarations():
    without, with_routes = BindingRegistry(), BindingRegistry()
    for registry in (without, with_routes):
        registry.allocate(object(), 'owner', 'value', LOC)
    with_routes.route_id(1, ('field',), 'int64', LOC)
    assert without.allocate_param('next', 'int64', LOC).id == with_routes.allocate_param('next', 'int64', LOC).id


def test_rollback_preserves_old_routes_and_discards_all_new_metadata():
    registry = BindingRegistry()
    owner = registry.allocate(object(), 'owner', 'value', LOC)
    old = [registry.route_id(owner.id, (name,), 'int64', LOC) for name in ('a', 'b', 'c')]
    saved = registry.next_id, registry.next_route_id
    assert max(old) > saved[0]
    extra = registry.allocate(object(), 'temporary', 'value', LOC)
    new_route = registry.route_id(owner.id, ('extra',), 'int64', LOC)
    other_route = registry.route_id(extra.id, ('extra',), 'int64', LOC)
    registry.index_routes = {owner.id: {old[0], new_route}, extra.id: {other_route}}
    registry.rollback_allocations(*saved)
    assert set(registry.by_id) == {owner.id, *old}
    assert set(registry.route_paths) == set(old)
    assert set(registry.by_syntax) == {id(owner.syntax)}
    assert registry.routes_by_root == {owner.id: old}
    assert registry.index_routes == {owner.id: {old[0]}}
    assert registry.allocate_param('reused', 'int64', LOC).id == extra.id
    assert registry.route_id(owner.id, ('replacement',), 'int64', LOC) == new_route
