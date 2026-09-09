"""Object ownership survives renaming and distinguishes shadowed bindings."""

from dataclasses import replace

from dewy.backend.udewy.lower import _Lowerer
from dewy.parser import t0
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty


def test_object_releases_follow_binding_identity(monkeypatch) -> None:
    loc = Span(0, 0)
    root = hir.Block(loc, ty.VOID_TYPE, [], True)
    lowerer = _Lowerer(root, SrcFile(None, ''))
    record = ty.ObjectType((ty.ObjectField('text', 'string'),))
    declaration = hir.Declare(loc, ty.VOID_TYPE, 'let', 'item', record, hir.Void(loc, ty.VOID_TYPE), binding_id=1)
    lowerer._note_owned_object(declaration, record)

    # The owned binding has been renamed during lowering. Another binding
    # uses its old spelling; that must neither inherit ownership nor release.
    pointer = hir.Integer(loc, 'int64', t0.base10, 0)
    renamed = replace(declaration, name='renamed', annotation='int64', expr=pointer)
    shadow = replace(renamed, name='item', binding_id=2)
    body = replace(root, items=[renamed, hir.Block(loc, ty.VOID_TYPE, [shadow], True)])
    releases = []

    def release(value, object_type, loc):
        releases.append((value.name, value.binding_id, object_type))
        return []

    monkeypatch.setattr(lowerer, '_release_object_members', release)
    lowerer._insert_releases(body)
    assert releases == [('renamed', 1, record)]
    assert lowerer._place_is_owned(hir.ExpressedIdentifier(loc, record, 'renamed', binding_id=1))
    assert not lowerer._place_is_owned(hir.ExpressedIdentifier(loc, record, 'item', binding_id=2))
