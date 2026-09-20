"""Reserved source bindings, without changing expression-token shapes.

`none`, `void` and `end` still participate in ordinary expression/type/index
parsing. Reservation prevents user bindings from shadowing those roles; it
must not reject the compiler's synthesized last-index binding.
"""
from ..parser import p0, t1, t2
from ..reporting import Pointer
from .errors import user_error

RESERVED = frozenset({'extern', 'intrinsic', 'none', 'void', 'end', 'new'})


def symbol(node):
    if isinstance(node, p0.BinOp) and isinstance(node.op, t1.Operator):
        return node.op.symbol
    return None


def validate(root, srcfile):
    def bound(node, pattern=False):
        if pattern and isinstance(node, p0.Block) and node.kind == '<>':
            return
        if isinstance(node, p0.Atom) and isinstance(node.item, t1.Identifier):
            if node.item.name in RESERVED:
                user_error(srcfile, f'`{node.item.name}` is reserved',
                           Pointer(span=node.loc, message='choose another binding name'))
        elif isinstance(node, p0.Block):
            for item in node.inner:
                bound(item, pattern)
        elif isinstance(node, p0.Flat):
            for item in node.items:
                bound(item, pattern)
        elif isinstance(node, p0.Prefix):
            bound(node.item, pattern)
        elif isinstance(node, p0.BinOp):
            if symbol(node) in {':', '=', ':=', '::', 'of'}:
                bound(node.left)
            elif symbol(node) == '.':
                bound(node.right)
            elif isinstance(node.op, t2.EllipsisJuxtapose):
                bound(node.right)
            elif symbol(node) == ':>':
                bound(node.left)
            elif isinstance(node.op, t2.TypeParamJuxtapose):
                bound(node.left)
                bound(node.right)

    def imported(node):
        if isinstance(node, p0.Block):
            for item in node.inner:
                imported(item)
        elif isinstance(node, p0.Flat):
            for item in node.items:
                imported(item)
        else:
            bound(node.right if symbol(node) == 'as' else node)

    pending = [root]
    match_arms = set()
    while pending:
        node = pending.pop()
        op = symbol(node)
        if op in {':', '=', ':=', '::', 'in'}:
            bound(node.left)
        elif op == '=>':
            bound(node.left, id(node) in match_arms)
        elif isinstance(node, p0.KeywordExpr) and node.parts:
            first = node.parts[0]
            if isinstance(first, t1.Keyword):
                if first.name == 'match' and len(node.parts) == 3 and isinstance(node.parts[2], p0.Block):
                    match_arms.update(id(arm) for arm in node.parts[2].inner)
                if first.name in {'let', 'const', 'local_const'} and len(node.parts) == 2:
                    bound(node.parts[1])
                elif first.name == 'from' and len(node.parts) == 4:
                    imported(node.parts[3])
                elif first.name == 'import':
                    if len(node.parts) == 4:
                        imported(node.parts[1])
                    elif len(node.parts) == 2 and symbol(node.parts[1]) == 'as':
                        bound(node.parts[1].right)
        pending.extend(p0.children(node))
