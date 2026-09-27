"""Validate the initial read-only `$lend` subset before allowing unpinned access.

A scoped address remains an ordinary machine word at runtime. Its provenance
is tracked through local expressions and assignments here; it cannot become
an enclosing binding, result, capture, or unknown call argument. Only modeled
synchronous consumers may receive it. This pass grants a lowering permission,
not a blanket exemption for raw operations in the surrounding function.
"""
from . import hir, ty
from .errors import user_error
from ..reporting import Pointer

# The raw subset deliberately excludes user-defined operators. Their spelling
# cannot establish purity, receiver stability or an address lifetime.
SCALARS = frozenset({
    '__add__', '__sub__', '__mul__', '__div__', '__floordiv__', '__mod__',
    '__unary_sub__', '__not__', '__eq__', '__ne__', '__lt__', '__le__',
    '__gt__', '__ge__', '__and__', '__or__', '__xor__', '__nand__', '__nor__',
    '__xnor__', '__lshift__', '__rshift__',
})
LOADS = frozenset(f'__load_{word}__' for word in ('i8', 'u8', 'i16', 'u16', 'i32', 'u32', 'i64', 'u64'))


def validate_read(owner, body, source, *, target, writable=False):
    def reject(node, detail):
        user_error(source, 'cannot prove scoped storage access',
                   Pointer(span=node.loc, message=detail),
                   Pointer(span=owner.loc, message='storage is lent here', color='blue'))

    shape = ty.structural_base(owner.type)
    if (not isinstance(owner, hir.ExpressedIdentifier) or owner.binding_id is None
            or not isinstance(shape, ty.ArrayType) or ty.strip_refinement(shape.element) != 'uint8'):
        reject(owner, 'this read-only loan currently requires a named byte array')
    root = owner.binding_id
    nodes = list(hir.walk(body))
    local = {node.binding_id for node in nodes if isinstance(node, hir.Declare)}
    addresses = set()
    checked_reads = []

    def intrinsic(node):
        callee = node.func
        if isinstance(callee, hir.ExpressedIdentifier) and callee.binding_id is None and not node.kw_args:
            return callee.name
        return None

    def extraction(node):
        return (isinstance(node, hir.FunctionCall) and intrinsic(node) == '__load_i64__'
                and len(node.pos_args) == 1 and isinstance(node.pos_args[0], hir.ExpressedIdentifier)
                and node.pos_args[0].binding_id == root)

    def derived(node):
        if isinstance(node, (hir.Declare, hir.Assign, hir.Void, hir.Break, hir.Continue)):
            return False
        if isinstance(node, hir.Block):
            return any(derived(item) for item in node.items if item.type not in ('void', 'never'))
        if extraction(node):
            return True
        if isinstance(node, hir.ExpressedIdentifier):
            return node.binding_id in addresses
        if isinstance(node, hir.FunctionCall) and intrinsic(node) in LOADS | {'__syscall3__'}:
            # A memory read returns the stored word, and write(2) returns a
            # count/error. Neither returns the address of its input storage.
            return False
        return any(derived(child) for child in hir.children(node))

    # One finite set per scope. Branch joins and loop backedges retain every
    # possible address origin rather than trusting source traversal order.
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if isinstance(node, hir.Declare):
                binding, value = node.binding_id, node.expr
            elif isinstance(node, hir.Assign) and isinstance(node.target, hir.ExpressedIdentifier):
                binding, value = node.target.binding_id, node.value
            else:
                continue
            if binding not in addresses and derived(value):
                addresses.add(binding)
                changed = True

    def visit(node, *, result=False):
        if result and derived(node):
            reject(node, 'an address derived from lent storage cannot leave its scope')
        if isinstance(node, hir.Block):
            for item in node.items:
                visit(item, result=item.type not in ('void', 'never'))
            return
        if isinstance(node, hir.FunctionCall):
            if isinstance(node.func, hir.ArrayMethod) and node.func.name == 'set_length':
                if (not writable or not isinstance(node.func.array, hir.ExpressedIdentifier)
                        or node.func.array.binding_id != root):
                    reject(node, 'only the writable loan owner can commit its length')
                for argument in [*node.pos_args, *node.kw_args.values()]:
                    if derived(argument):
                        reject(argument, 'an address cannot be committed as a length')
                    visit(argument)
                return
            name = intrinsic(node)
            if extraction(node):
                checked_reads.append(node)
                return
            if name == '__syscall3__':
                args = node.pos_args
                # Linux x86-64 write(2) consumes the source synchronously.
                # Other syscall numbers have no such permission here.
                if (target not in ('x86_64', 'c') or len(args) != 4 or not isinstance(args[0], hir.Integer) or args[0].value not in ({0, 1} if writable else {1})
                        or any(derived(args[index]) for index in (0, 1, 3))
                        or args[0].value == 0 and not derived(args[2])):
                    reject(node, 'only synchronous write consumes a scoped address in this initial subset')
            elif writable and name == '__store_u8__':
                if len(node.pos_args) != 2 or derived(node.pos_args[0]) or not derived(node.pos_args[1]):
                    reject(node, 'write only scalar bytes through the lent address')
            elif name not in SCALARS | LOADS:
                reject(node, 'this call has no checked scoped-storage lifetime')
            for argument in node.pos_args:
                visit(argument)
            if name in LOADS or name == '__syscall3__':
                checked_reads.append(node)
            return
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id == root:
                reject(node, 'use the lent owner only to obtain its address or read its length')
            if not isinstance(ty.strip_refinement(node.type), (str, ty.IntegerLiteralType)):
                reject(node, 'this subset permits scalar local work while storage is lent')
            return
        if isinstance(node, hir.ArrayLength):
            if isinstance(node.array, hir.ExpressedIdentifier) and node.array.binding_id == root:
                return
            reject(node, 'only the lent owner\'s length is available in this raw scope')
        if isinstance(node, hir.Declare):
            if node.view or not isinstance(ty.strip_refinement(node.expr.type), (str, ty.IntegerLiteralType)):
                reject(node, 'a raw scope may only declare scalar local values')
            visit(node.expr)
            return
        if isinstance(node, hir.Assign):
            if not isinstance(node.target, hir.ExpressedIdentifier) or node.target.binding_id not in local:
                reject(node, 'a raw scope may only assign its own scalar locals')
            visit(node.value)
            return
        if isinstance(node, hir.Return):
            if node.item is not None:
                visit(node.item, result=True)
            return
        if isinstance(node, (hir.Integer, hir.Bool, hir.Void, hir.Break, hir.Continue, hir.NoneValue)):
            return
        if isinstance(node, hir.Assert):
            if node.runtime or node.expect:
                reject(node, 'runtime reporting is outside the raw-scope subset')
            visit(node.condition)
            return
        if isinstance(node, (hir.Flow, hir.IfArm, hir.LoopArm, hir.ShortCircuit, hir.Suppress,
                             hir.ValueCast, hir.RepresentationCast, hir.Transmute, hir.Obligation)):
            for child in hir.children(node):
                visit(child)
            return
        reject(node, 'this operation is outside the initial read-only raw-scope subset')

    visit(body, result=True)
    # Grant the narrowly scoped permission only after every use is checked.
    for node in checked_reads:
        node.scoped_read = True
