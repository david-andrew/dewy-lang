"""Nominal fast paths preserve the Boolean subtype relation as graphs change."""
from dewy.semantic import ty


def test_nominal_queries_match_boolean_differences():
    system = ty.TypeSystem()
    system.add_type('First')
    system.add_type('Second')
    system.add_type('Both', 'First')
    system.add_type_link('Both', 'Second')
    names = [*system._named_types, 'void', 'untyped', 'unknown-nominal']
    for source in names:
        for target in names:
            expected = system.is_empty(ty.intersect(source, ty.negate(target)))
            assert system.is_subtype(source, target) == expected, (source, target)


def test_reachability_expires_when_the_graph_changes():
    system = ty.TypeSystem(['First', 'Second', 'Child'])
    assert not system.is_subtype('Child', 'First')
    assert not system.is_subtype('Child', 'Second')
    system.add_type_link('Child', 'First')
    assert system.is_subtype('Child', 'First')
    assert not system.is_subtype('Child', 'Second')
    system.add_type_link('First', 'Second')
    assert system.is_subtype('Child', 'Second')
    # Cycles retain the existing graph semantics and terminate.
    system.add_type_link('Second', 'Child')
    assert system.is_subtype('Second', 'First')
    other = ty.TypeSystem(['First', 'Second', 'Child'])
    assert not other.is_subtype('Child', 'First')
