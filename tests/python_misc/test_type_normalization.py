"""Normalization preserves metadata and observes changing type structures."""
from dewy.semantic import ty


def test_unchanged_record_family_needs_no_dataclass_reconstruction(monkeypatch):
    leaf = ty.ObjectType((ty.ObjectField('n', 'int64'),))
    value = ty.ObjectType((ty.ObjectField('items', ty.ArrayType(leaf)),
                           ty.ObjectField('maybe', ty.TypeOr([leaf, 'none']))))
    def unexpected(*args, **kwargs):
        raise AssertionError('normalizing an unchanged record reconstructed a dataclass')
    monkeypatch.setattr(ty, 'replace', unexpected)
    assert ty.to_nnf(value) is value
    assert ty.normalize(value)


def test_changed_nested_field_retains_record_and_field_metadata():
    default, scope = object(), object()
    stable = ty.ObjectField('stable', 'bool')
    field = ty.ObjectField('items', ty.ArrayType(ty.TypeNot(ty.TypeNot('int64')), 4),
                           mutable=False, default=default, default_scope=scope)
    original = ty.ObjectType((stable, field), brand='normalization-test', immutable=True)
    normalized = ty.to_nnf(original)
    assert normalized is not original
    assert normalized.fields[0] is stable
    assert normalized.fields[1].type == ty.ArrayType('int64', 4)
    assert normalized.fields[1].default is default
    assert normalized.fields[1].default_scope is scope
    assert not normalized.fields[1].mutable
    assert normalized.brand == original.brand and normalized.immutable
    assert original.fields[1].type.element == ty.TypeNot(ty.TypeNot('int64'))


def test_mutable_children_are_revisited_after_normalization():
    choice = ty.TypeOr(['int64', 'none'])
    array = ty.ArrayType(choice)
    assert ty.to_nnf(array) is array
    choice.items.append(ty.TOP_TYPE)
    assert ty.to_nnf(array) == ty.ArrayType(ty.TOP_TYPE)
    choice.items[:] = ['int64', ty.TypeNot(ty.TypeNot('bool'))]
    assert ty.to_nnf(array) == ty.ArrayType(ty.TypeOr(['int64', 'bool']))


def test_smart_constructor_reductions_still_apply_inside_records():
    original = ty.ObjectType((ty.ObjectField('value', ty.TypeAnd([
        ty.TOP_TYPE, ty.TypeOr(['int64', ty.BOTTOM_TYPE])])),))
    assert ty.to_nnf(original).fields[0].type == 'int64'
    negated = ty.to_nnf(ty.TypeNot(ty.TypeOr(['int64', 'bool'])))
    assert negated == ty.TypeAnd([ty.TypeNot('int64'), ty.TypeNot('bool')])
