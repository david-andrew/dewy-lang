"""Values that leave an `$allocator(@arena) { ... }` block.

Such a value is copied out to the enclosing allocator (see
PHASE1_DESIGN_PROPOSALS, "Context allocators"). This first rule is lexical
and shared by both lowerings, so reports and `$explicit_copies` acceptance
agree whatever each implementation does with the allocation itself:

- the block's result value;
- an assignment to a binding declared outside the block;
- a store into storage rooted at such a binding (a field, an element, a
  dictionary entry, `push`/`insert`);
- a `return` from inside the block.

A nested function literal's body runs only when called and is not part of
the block's lexical extent. Mirrors `allocator_escapes.dewy`.
"""
from dataclasses import dataclass

from . import hir
from ..reporting import Span


@dataclass(frozen=True)
class Escape:
    loc: Span
    value_type: object
    site: str
    arena: str
    explicit: bool = False   # the value is written as an explicit `.copy()`


def _root(node: hir.AST) -> int | None:
    while True:
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        elif isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute, hir.Suppress)):
            node = node.expr if not isinstance(node, hir.Suppress) else node.item
        elif isinstance(node, hir.MemberAccess):
            node = node.value
        elif isinstance(node, hir.Index):
            node = node.array
        elif isinstance(node, hir.DictLookup):
            node = node.values
        else:
            return node.binding_id if isinstance(node, hir.ExpressedIdentifier) else None


def _name(node: hir.AST) -> str:
    while not isinstance(node, hir.ExpressedIdentifier):
        if isinstance(node, hir.MemberAccess):
            node = node.value
        elif isinstance(node, hir.Index):
            node = node.array
        elif isinstance(node, hir.DictLookup):
            node = node.values
        elif isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            node = node.expr
        else:
            return 'outer storage'
    return f'`{node.name}`'


def _explicit(value: hir.AST) -> bool:
    while isinstance(value, (hir.ValueCast, hir.RepresentationCast, hir.Suppress)) or (
            isinstance(value, hir.Block) and not value.scoped and len(value.items) == 1):
        value = value.item if isinstance(value, hir.Suppress) else value.items[0] if isinstance(value, hir.Block) else value.expr
    return isinstance(value, hir.CopyValue)


def _escape(value: hir.AST, site: str, arena: str) -> 'Escape':
    return Escape(value.loc, value.type, site, arena, _explicit(value))


def _last_value(block: hir.Block) -> hir.AST | None:
    if block.type in ('void', None) or not block.items:
        return None
    return block.items[-1]


def escapes(root: hir.AST) -> list[Escape]:
    """Every lexical escape of every allocator block under ``root``."""
    found: list[Escape] = []
    for node in hir.walk(root):
        if isinstance(node, hir.AllocatorBlock):
            found.extend(_block_escapes(node))
    return found


def _arena_name(block: hir.AllocatorBlock) -> str:
    target = block.arena.target if isinstance(block.arena, hir.Place) else block.arena
    return _name(target).strip('`')


def _block_escapes(block: hir.AllocatorBlock) -> list[Escape]:
    arena = _arena_name(block)
    declared: set[int] = set()
    nodes: list[hir.AST] = []
    pending: list[hir.AST] = list(reversed(block.items))
    while pending:
        node = pending.pop()
        if isinstance(node, hir.FunctionLiteral):
            continue
        nodes.append(node)
        if isinstance(node, hir.Declare) and node.binding_id is not None:
            declared.add(node.binding_id)
        if isinstance(node, hir.IteratorExpression) and node.target.binding_id is not None:
            declared.add(node.target.binding_id)
        pending.extend(reversed(list(hir.children(node))))
    found: list[Escape] = []
    result = _last_value(block)
    if result is not None:
        found.append(_escape(result, 'produced as the block result', arena))

    def outer(target: hir.AST) -> bool:
        binding = _root(target)
        return binding is None or binding not in declared

    for node in nodes:
        if isinstance(node, hir.Assign) and node.target.binding_id not in declared:
            found.append(_escape(node.value, f'stored into `{node.target.name}`', arena))
        elif isinstance(node, (hir.MemberAssign, hir.IndexAssign)) and outer(node.target):
            found.append(_escape(node.value, f'stored into {_name(node.target)}', arena))
        elif isinstance(node, hir.DictStore) and node.value is not None and outer(node.keys):
            found.append(_escape(node.value, f'stored into {_name(node.keys)}', arena))
        elif (isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod)
              and node.func.name in ('push', 'insert') and outer(node.func.array)):
            value = node.pos_args[0] if node.func.name == 'push' and node.pos_args else (
                node.pos_args[1] if len(node.pos_args) > 1 else node.kw_args.get('value'))
            if value is not None:
                found.append(_escape(value, f'stored into {_name(node.func.array)}', arena))
        elif isinstance(node, hir.Return) and node.item is not None:
            found.append(_escape(node.item, 'returned', arena))
    return found
