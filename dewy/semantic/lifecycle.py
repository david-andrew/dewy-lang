"""Structural ownership queries shared by lifecycle checking.

A custom copy hook owns the construction of its complete result. Without
one, the synthesized operation must be able to copy each stored component.
These queries describe capabilities, not copy elision or runtime hook calls.
"""
from dataclasses import dataclass

from . import ty


@dataclass(frozen=True)
class CopyBlocker:
    owner: ty.ObjectType
    path: str


def copy_blocker(type_: ty.Type) -> CopyBlocker | None:
    """Find a drop-only component that a synthesized copy would duplicate.

    Unions require a copy for any possible active alternative. Recursive
    records are visited once; a cycle alone is not evidence of move-only
    storage. A custom hook may construct fresh members independently, so
    its own fields do not constrain whether that hook can be invoked.
    """
    pending = [(type_, '')]
    seen = set()
    while pending:
        type_, path = pending.pop()
        type_ = ty.unfold(ty.strip_refinement(type_))
        if id(type_) in seen:
            continue
        seen.add(id(type_))
        if isinstance(type_, ty.ObjectType):
            roles = {method.lifecycle for method in type_.methods}
            if 'copy' in roles:
                continue
            if 'drop' in roles:
                return CopyBlocker(type_, path)
            pending.extend((field.type, f'{path}.{field.name}') for field in reversed(type_.fields))
        elif isinstance(type_, ty.ArrayType):
            pending.append((type_.element, path + '[]'))
        elif isinstance(type_, ty.TypeOr):
            pending.extend((member, path) for member in reversed(type_.items))
    return None
