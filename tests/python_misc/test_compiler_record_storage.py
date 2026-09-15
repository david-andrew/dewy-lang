"""Compact compiler records retain graph identity and serialization behavior."""
from dataclasses import replace
import pickle
import weakref

from dewy.reporting import Span
from dewy.semantic import hir, ty
from dewy.semantic.analyze.bounds import Interval


def test_recursive_type_and_hir_graph_survive_pickle_and_replacement():
    reference = ty.NamedType('Node', 123)
    record = ty.ObjectType((ty.ObjectField('next', ty.TypeOr(['none', reference])),))
    reference.resolve(record)
    loc = Span(3, 7)
    node = hir.ExpressedIdentifier(loc, record, 'value', binding_id=42)
    default = hir.BoundParam('value', record, node, binding_id=43)
    restored, alias, parameter = pickle.loads(pickle.dumps((node, reference, default)))
    assert alias.target is restored.type
    assert restored.type.fields[0].type.items[1] is alias
    assert parameter.value is restored and parameter.type is restored.type
    assert restored.loc == loc and restored.binding_id == 42
    renamed = replace(restored, name='renamed')
    assert renamed.type is restored.type and renamed.loc is restored.loc
    assert renamed.binding_id == 42 and restored.name == 'value'
    assert weakref.ref(renamed)() is renamed
    assert pickle.loads(pickle.dumps(Interval(0, 7, capped=True))).capped


def test_path_literal_initializes_all_inherited_storage_fields():
    path = ty.PathLiteralType('folder/file.dewy')
    restored = pickle.loads(pickle.dumps(path))
    assert restored == path
    assert restored.immutable is False
    assert restored.constructors == []
    assert restored.fields[0].type == ty.StringLiteralType('folder/file.dewy')


def test_guard_search_position_survives_hir_rewrites():
    loc = Span(0, 1)
    key = hir.String(loc, ty.StringLiteralType('key'), 'key')
    keys = hir.ExpressedIdentifier(loc, ty.ArrayType(ty.StringType(), None), 'keys')
    guard = hir.DictContains(loc, 'bool', keys, key, position='position', hoisted=True)
    rewritten = replace(guard, key=replace(key, content='other'))
    assert pickle.loads(pickle.dumps(rewritten)).hoisted
    assert rewritten.position == 'position'
