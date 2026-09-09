"""Access paths retain identity, index expressions, and consumer cast policy."""

from dewy.reporting import Span
from dewy.semantic import bindings as sb
from dewy.semantic import hir, ty


def test_access_paths_retain_index_expressions_and_distinguish_fields() -> None:
    loc = Span(0, 0)
    element = ty.ObjectType((ty.ObjectField('text', 'string'),))
    array = ty.ArrayType(element)
    root = hir.ExpressedIdentifier(loc, ty.ObjectType((ty.ObjectField('items', array),)), 'bag', binding_id=1)
    items = hir.MemberAccess(loc, array, root, 'items')
    index = hir.ExpressedIdentifier(loc, 'int64', 'i', binding_id=2)
    item = hir.Index(loc, element, items, index, None)
    text = hir.MemberAccess(loc, 'string', item, 'text')
    path = sb.access_path(text)
    assert path.binding_id == 1
    assert path.components == (('field', 'items'), ('index', None), ('field', 'text'))
    assert path.steps[1].index is index
    assert sb.member_path(text) is None
    assert sb.member_path(items) == (1, ('items',))


def test_fact_routes_opt_into_cast_transparency() -> None:
    loc = Span(0, 0)
    record = ty.ObjectType((ty.ObjectField('text', 'string'),))
    registry = sb.BindingRegistry()
    binding = registry.allocate_param('bag', record, loc)
    root = hir.ExpressedIdentifier(loc, record, 'bag', binding_id=binding.id)
    viewed = hir.RepresentationCast(loc, record, root)
    text = hir.MemberAccess(loc, 'string', viewed, 'text')
    assert sb.access_path(text).binding_id is None
    plain_text = hir.MemberAccess(loc, 'string', root, 'text')
    assert sb.array_route_id(text, registry) == sb.array_route_id(plain_text, registry)
    assert registry.route_paths[sb.array_route_id(text, registry)] == ('text',)
