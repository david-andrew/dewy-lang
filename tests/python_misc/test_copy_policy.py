"""Finite outer layouts do not imply bounded transitive value copies."""
import pytest
from dewy.backend.udewy.copy_policy import runtime_sized
from dewy.semantic import ty


@pytest.mark.parametrize('type_,expected', [
    ('int64', False),
    (ty.StringLiteralType('hello'), False),
    ('string', True),
    (ty.StringType(1), True),  # a grapheme has arbitrarily many combining marks
    (ty.StringType(0), False),
    (ty.ArrayType('uint8', 16), False),
    (ty.ArrayType('uint8'), True),
    (ty.ArrayType('string', 0), False),
    (ty.ArrayType('string', 1), True),
    (ty.ObjectType((ty.ObjectField('data', ty.ArrayType('uint8')),)), True),
    (ty.TypeOr([ty.ArrayType('uint8'), 'none']), True),
    (ty.TypeOr([ty.StringLiteralType('a'), ty.StringLiteralType('bb')]), False),
])
def test_transitive_copy_bound(type_, expected):
    assert runtime_sized(type_) is expected


def test_repeated_finite_field_type_is_not_a_recursive_copy():
    inner = ty.ObjectType((ty.ObjectField('value', 'int64'),))
    outer = ty.ObjectType((ty.ObjectField('left', inner), ty.ObjectField('right', inner)))
    assert not runtime_sized(outer)


def test_parent_copy_includes_runtime_sized_child_fields(monkeypatch):
    parent = ty.ObjectType((ty.ObjectField('value', 'int64'),), brand='Root')
    child = ty.ObjectType((*parent.fields, ty.ObjectField('data', 'string')), brand='Child')
    monkeypatch.setattr(ty, 'USER_BRAND_TYPES', {'Root': parent, 'Child': child})
    monkeypatch.setattr(ty, 'USER_BRAND_PARENTS', {'Child': 'Root'})
    monkeypatch.setattr(ty, 'USER_BRANDS', {'Root', 'Child'})
    assert runtime_sized(parent)
    assert runtime_sized(ty.ObjectType(parent.fields))


def test_native_copy_bound_classification(tmp_path):
    from pathlib import Path
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile
    from test_scalar_projection import execute

    source = Path(__file__).resolve().parents[2] / 'tests/fixtures/native_copy_policy.dewy'
    execute(tmp_path, 'native-copy-bound', codegen(SrcFile.from_path(source), debug_locations=False))
