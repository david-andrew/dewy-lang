"""The approved explicit-copy policy, applied to storage decisions.

A fixed outer record or array can still contain runtime-sized storage.
String length counts graphemes, not bytes: even one grapheme has no fixed
byte bound. Facts and COW handles do not by themselves bound the copy.
"""
from ...semantic import ty


def runtime_sized(type_: ty.Type, memo: dict[int, tuple[ty.Type, bool]] | None = None) -> bool:
    active: set[int] = set()
    memo = {} if memo is None else memo

    def visit(type_: ty.Type) -> bool:
        plain = ty.unfold(ty.strip_refinement(type_))
        identity = id(plain)
        if identity in active:
            return True  # recursive owned storage has no finite copy bound
        if identity in memo:
            return memo[identity][1]
        if isinstance(plain, str):
            return plain in {'string', 'char', 'grapheme'}
        if isinstance(plain, ty.StringType):
            return plain.length != 0
        if isinstance(plain, ty.ArrayType) and plain.length is None:
            return True
        active.add(identity)
        if isinstance(plain, ty.ArrayType):
            children = [] if plain.length == 0 else [plain.element]
        elif isinstance(plain, ty.ObjectType):
            children = [field.type for field in plain.fields]
            # Copy dispatch preserves a concrete child's extra fields, even
            # through a parent or structural view.
            for brand in ty.brand_alternatives(plain):
                child = ty.USER_BRAND_TYPES.get(brand)
                if child is not None:
                    children.extend(field.type for field in child.fields
                                    if plain.field(field.name) is None)
        elif isinstance(plain, (ty.TypeOr, ty.TypeAnd)):
            children = plain.items
        else:
            children = []
        result = any(visit(child) for child in children)
        active.remove(identity)
        memo[identity] = (plain, result)
        return result

    return visit(type_)


def validate(notes, sources) -> None:
    from ...reporting import Pointer
    from ...semantic.errors import user_error
    # This is checked-HIR metadata, not a CLI rescan. It also survives module
    # assembly, renaming, proof erasure and direct lowering API calls.
    policies = {source.path for source in sources}
    for note in notes:
        if note.explicit or not note.runtime_sized:
            continue
        if note.srcfile.path not in policies:
            continue
        user_error(note.srcfile, 'unproven copy',
                   Pointer(span=note.loc, message=note.line),
                   hint='use `.copy()` for an independent value, or a required read-only view when the source can stay stable',
                   notes=['This module enables `$explicit_copies`; COW sharing does not prove that a logical copy is free.'])
