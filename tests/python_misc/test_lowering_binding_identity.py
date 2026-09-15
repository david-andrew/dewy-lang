"""Object ownership survives renaming and distinguishes shadowed bindings."""

from dataclasses import replace

from dewy.backend.udewy.lower import _Lowerer, _uniquify_module_locals
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


def test_local_renaming_preserves_shared_subtrees_and_original_bindings():
    loc = Span(0, 0)
    value = hir.Integer(loc, 'int64', t0.base10, 42)
    first = hir.Declare(loc, 'void', 'let', 'x', 'int64', value, binding_id=1)
    second = replace(first, binding_id=2)
    original_use = hir.ExpressedIdentifier(loc, 'int64', 'x', binding_id=2)
    shared = original_use
    for _ in range(24):
        shared = hir.Block(loc, 'int64', [shared, shared], False)
    body = hir.Block(loc, 'int64', [first, second, shared], True)
    literal = hir.FunctionLiteral(loc, ty.FunctionType([], [], None, 'int64'),
                                  [], [], None, 'int64', body)
    root = hir.Block(loc, 'void', [literal, literal], False)
    renamed = _uniquify_module_locals(root)
    assert renamed.items[0] is renamed.items[1]
    first, second, shared = renamed.items[0].body.items
    assert (first.name, second.name) == ('x', 'x__2')
    for _ in range(24):
        assert shared.items[0] is shared.items[1]
        shared = shared.items[0]
    assert (shared.name, shared.binding_id) == ('x__2', 2)
    assert original_use.name == 'x' and literal.body.items[1].name == 'x'


def test_generated_intrinsic_signatures_keep_types_and_compilation_lifetime():
    loc = Span(0, 0)
    root = hir.Block(loc, 'void', [], False)
    first = _Lowerer(root, SrcFile(None, ''))
    second = _Lowerer(root, SrcFile(None, ''))
    word = hir.Integer(loc, 'int64', t0.base10, 42)
    byte = replace(word, type='uint8')
    call = first._intrinsic_call('__load_u8__', [word], 'uint8', loc)
    assert call.func.type.pos_or_kw == [ty.PosOrKwArg(None, 'int64')]
    assert call.func.type.ret == 'uint8'
    changed = first._intrinsic_call('__load_u8__', [byte], 'uint8', loc)
    assert changed.func.type.pos_or_kw == [ty.PosOrKwArg(None, 'uint8')]
    assert changed.func.type is not call.func.type
    other = second._intrinsic_call('__load_u8__', [word], 'uint8', loc)
    assert other.func.type == call.func.type and other.func.type is not call.func.type
    binary = first._int64_binary('__add__', word, word, loc)
    assert binary.func.type.pos_or_kw == [ty.PosOrKwArg('left', 'int64'), ty.PosOrKwArg('right', 'int64')]
