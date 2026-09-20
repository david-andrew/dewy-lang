"""Resolve public effect subjects without admitting effects as value types."""
from dataclasses import replace

from ..parser import p0, t1, t2
from ..reporting import Pointer
from . import effect_rows as rows, ty
from .errors import user_error

FAMILIES = frozenset({'reads', 'mutates'})


def unparen(ast):
    while isinstance(ast, p0.Block) and ast.kind == '()' and len(ast.inner) == 1:
        ast = ast.inner[0]
    return ast


def name(ast):
    ast = unparen(ast)
    return ast.item.name if isinstance(ast, p0.Atom) and isinstance(ast.item, t1.Identifier) else None


def application(ast):
    ast = unparen(ast)
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t2.TypeParamJuxtapose):
        block = ast.right
        if isinstance(block, p0.Block) and block.kind == '<>':
            return name(ast.left), block.inner
    return name(ast), None


def row_binding(ast, ctx):
    identifier = name(ast)
    binding = ctx.binding_scopes.get(identifier) if identifier is not None else None
    return binding.effect_value if binding is not None and binding.kind == 'effect' else None


def is_effect(ast, ctx):
    ast = unparen(ast)
    if isinstance(ast, p0.Prefix) and ast.op.symbol == 'no':
        return True
    head, _ = application(ast)
    return head in FAMILIES | {'no_effects', 'Effect'} or row_binding(ast, ctx) is not None


def split(ast, ctx):
    """Keep value intersections intact, collecting only effect-kind terms."""
    ast = unparen(ast)
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol == '&':
        left, before = split(ast.left, ctx)
        right, after = split(ast.right, ctx)
        value = right if left is None else left if right is None else replace(ast, left=left, right=right)
        return value, [*before, *after]
    return (None, [ast]) if is_effect(ast, ctx) else (ast, [])


def route(ast):
    ast = unparen(ast)
    root = name(ast)
    if root is not None:
        return root, ()
    if isinstance(ast, p0.BinOp) and isinstance(ast.op, t1.Operator) and ast.op.symbol == '.':
        prefix = route(ast.left)
        field = name(ast.right)
        if prefix is not None and field is not None:
            return prefix[0], (*prefix[1], field)
    return None


def contract(ast, parameters, ctx):
    from .check import ast_to_type

    _, terms = split(ast, ctx)
    if not terms:
        return None

    def fail(site, title, detail):
        user_error(ctx.srcfile, title, Pointer(span=site.loc, message=detail))

    def subject(site):
        path = route(site)
        if path is not None:
            root, fields = path
            for index, parameter in enumerate(parameters):
                if parameter.name != root:
                    continue
                if not parameter.place:
                    fail(site, 'effect subject is not caller-owned storage', 'use a place parameter or a nominal resource identity')
                current = parameter.type
                for field in fields:
                    current = ty.unfold(ty.strip_refinement(current))
                    member = next((item for item in current.fields if item.name == field), None) if isinstance(current, ty.ObjectType) else None
                    if member is None:
                        fail(site, 'invalid effect resource route', f'`{field}` is not a stored field of this place')
                    current = member.type
                return rows.Subject('parameter', str(index), fields)
        resource = ty.unfold(ast_to_type(site, ctx=ctx))
        if not isinstance(resource, ty.ObjectType) or not ty.user_branded(resource):
            fail(site, 'effect resource needs a nominal identity', 'declare a marker with `Resource = type of any`, or name a place parameter')
        return rows.Subject('resource', resource.brand)

    permitted = None
    excluded = []
    for term in terms:
        negative = isinstance(term, p0.Prefix) and term.op.symbol == 'no'
        value = unparen(term.item) if negative else term
        family, arguments = application(value)
        bound_row = row_binding(value, ctx)
        if bound_row is not None:
            if negative:
                fail(term, 'cannot exclude a row parameter', 'exclude a named effect family or resource instead')
            permitted = rows.union(permitted or rows.Row(), bound_row)
            continue
        if family == 'no_effects' and arguments is None or family == 'Effect' and arguments == []:
            if negative:
                fail(term, 'cannot exclude an empty effect row', 'use `no_effects` directly, or `no reads` to exclude a family')
            permitted = rows.union(permitted or rows.Row(), rows.Row())
            continue
        if family not in FAMILIES:
            fail(term, 'unknown effect family', 'the initial named families are `reads` and `mutates`')
        if arguments == []:
            fail(term, 'empty effect family application', f'use `no {family}` or `no_effects`; `<>` does not mean a family exclusion')
        if arguments is None:
            if not negative:
                fail(term, 'positive effect needs a resource', f'write `{family}<Resource>`')
            excluded.append(rows.Atom(family))
            continue
        atoms = [rows.Atom(family, subject(argument)) for argument in arguments]
        if negative:
            excluded.extend(atoms)
        else:
            permitted = rows.union(permitted or rows.Row(), rows.Row(tuple(atoms)))
    return rows.Contract(permitted, tuple(excluded))
