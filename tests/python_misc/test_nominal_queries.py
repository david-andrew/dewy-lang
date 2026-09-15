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


def test_structural_shortcuts_match_boolean_differences():
    system = ty.TypeSystem()
    union = ty.TypeOr(['int64', 'bool'])
    redundant = ty.TypeAnd([union, 'any'])
    field = lambda type_: ty.ObjectType((ty.ObjectField('value', type_),))
    from dataclasses import replace
    record = field(union)
    signature = ty.FunctionType([ty.PosOrKwArg('value', 'int64')], [], None, 'int64')
    shapes = [
        'any', 'never', 'int64', 'uint8', 'string', 'array', 'object', 'function',
        union, redundant, ty.TypeNot(union),
        ty.IntegerLiteralType(0), ty.IntegerLiteralType(256),
        ty.StringLiteralType('hello'), ty.StringType(), ty.StringType(5),
        ty.ArrayType(union), ty.ArrayType(redundant), ty.ArrayType(union, 2),
        ty.ArrayType('int64', 0), ty.ArrayType('never', 0),
        record, field(redundant), replace(record, immutable=True),
        field(ty.TypeAnd(['int64', 'bool'])),
        signature, replace(signature, ret='uint8'), ty.OverloadType([signature]),
    ]
    for source in shapes:
        for target in shapes:
            expected = system.is_empty(ty.intersect(source, ty.negate(target)))
            assert system.is_subtype(source, target) == expected, (source, target)


def test_proven_record_and_array_queries_skip_normalization(monkeypatch):
    system = ty.TypeSystem()
    shared = ty.TypeOr(['int64', 'bool'])
    source = ty.ArrayType(shared, 2)
    target = ty.ArrayType(shared)
    record = ty.ObjectType((ty.ObjectField('payload', source),))
    from dataclasses import replace
    immutable = replace(record, immutable=True)
    def unexpected(_type):
        raise AssertionError('an already proven atom should not be normalized')
    with monkeypatch.context() as patch:
        patch.setattr(ty, 'normalize', unexpected)
        assert system.is_subtype(source, target)
        assert system.is_subtype(record, immutable)
    # Input descriptions remain live; there is no persistent checker cache.
    different = ty.ArrayType(ty.TypeOr(['int64', 'string']))
    assert not system.is_subtype(source, different)
    different.element.items[:] = ['int64', 'bool']
    assert system.is_subtype(source, different)
