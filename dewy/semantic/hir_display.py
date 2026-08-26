"""HIR tree dump (`repr`) and Dewy pretty-printer (`str`)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..parser import p0, t0, t2
from . import builtins, hir, ty

# ---------------------------------------------------------------------------
# type → Dewy
# ---------------------------------------------------------------------------

def type_to_dewy(t: ty.Type) -> str:
    """Render a type as Dewy source syntax."""
    if isinstance(t, str):
        return t
    if isinstance(t, ty.TypeVariable):
        return t.name
    if isinstance(t, ty.RationalLiteralType):
        return f'{t.numerator}/{t.denominator}'
    if isinstance(t, ty.RefinedType):
        conditions = ' '.join(
            (f'i => i {p.op.replace("not=?", "not =?")} {p.value}' if p.subject == 'self' else f'{p.subject} {p.op.replace("not=?", "not =?")} {p.value}')
            for p in t.propositions
        )
        base = type_to_dewy(t.base)
        if base.endswith('>'):
            return f'{base[:-1]} {conditions}>'
        return f'{base}<{conditions}>'
    if isinstance(t, ty.IntegerLiteralType):
        return str(t.value)
    if isinstance(t, ty.StringLiteralType):
        return repr(t.value)
    if isinstance(t, ty.BinaryLiteralType):
        return f'0x"{t.value.hex()}"'
    if isinstance(t, ty.PathLiteralType):
        return f'p{t.value!r}'
    if isinstance(t, ty.PathType):
        return 'Path'
    if isinstance(t, ty.ModuleType):
        return 'module'
    if isinstance(t, ty.StringType):
        length = f'<length={t.length}>' if t.length is not None else ''
        return f'string{length}'
    if isinstance(t, ty.DimensionType):
        if not t.powers:
            return 'Dimensionless'
        return ' * '.join(
            name if exponent == 1 else f'{name}^{exponent}'
            for name, exponent in t.powers
        )
    if isinstance(t, ty.QuantityType):
        return f'{_type_atom_parens(t.number)} * {type_to_dewy(t.dimension)}'
    if isinstance(t, ty.TypeAnd):
        return ' & '.join(_type_atom_parens(x) for x in t.items)
    if isinstance(t, ty.TypeOr):
        return ' | '.join(_type_atom_parens(x) for x in t.items)
    if isinstance(t, ty.TypeNot):
        inner = t.type
        if isinstance(inner, (ty.TypeAnd, ty.TypeOr)):
            return f'~({type_to_dewy(inner)})'
        return f'~{type_to_dewy(inner)}'
    if isinstance(t, ty.TypeParameterize):
        args = ' '.join(type_to_dewy(a) for a in t.args)
        return f'{_type_atom_parens(t.t)}<{args}>'
    if isinstance(t, ty.ArrayType):
        length = f' length={t.length}' if t.length is not None else ''
        return f'array<{type_to_dewy(t.element)}{length}>'
    if isinstance(t, ty.ObjectType) and t.brand == 'set':
        element = ty.set_element(t)
        assert element is not None
        return f'set<{type_to_dewy(element)}>'
    if isinstance(t, ty.ObjectType) and t.brand == 'dict':
        key_value = ty.dict_key_value(t)
        assert key_value is not None
        return f'dict<{type_to_dewy(key_value[0])} {type_to_dewy(key_value[1])}>'
    if isinstance(t, ty.ObjectType):
        fields = ' '.join(
            f'{"const " if not field.mutable else ""}{field.name}:{type_to_dewy(field.type)}'
            for field in t.fields
        )
        return f'[{fields}]'
    if isinstance(t, ty.FunctionType):
        return _function_type_to_dewy(t)
    if isinstance(t, ty.OverloadType):
        return ' & '.join(_type_atom_parens(m) for m in t.methods)
    if isinstance(t, ty.SequenceType):
        return f'<{" ".join(type_to_dewy(x) for x in t.items)}>'
    raise TypeError(f'unexpected type for type_to_dewy: {t!r}')


def type_alias_value_to_dewy(value: ty.TypeAliasValue) -> str:
    if not isinstance(value, ty.GenericTypeAlias):
        return type_to_dewy(value)
    params = ' '.join(
        param.name
        if param.bound == ty.TOP_TYPE
        else f'{param.name} of {type_to_dewy(param.bound)}'
        for param in value.params
    )
    return f'<{params}>({type_to_dewy(value.body)})'


def _type_atom_parens(t: ty.Type) -> str:
    """Parenthesize a type when it needs grouping inside a larger type expression."""
    s = type_to_dewy(t)
    if isinstance(t, (ty.TypeAnd, ty.TypeOr, ty.OverloadType)):
        return f'({s})'
    return s


def _function_type_to_dewy(t: ty.FunctionType) -> str:
    """Render a structural function type, preserving named argument contracts."""
    parts: list[str] = []
    if t.type_params:
        gens = ' '.join(
            p.name if p.bound == ty.TOP_TYPE else f'{p.name} of {type_to_dewy(p.bound)}'
            for p in t.type_params
        )
        parts.append(f'<{gens}>')
    args: list[str] = []
    for a in t.pos_or_kw:
        argument = (
            type_to_dewy(a.type)
            if a.name is None
            else f'{a.name}:{type_to_dewy(a.type)}'
        )
        args.append(f'@{argument}' if a.place else argument)
    if t.rest is not None or t.kw_only:
        args.append(f'...{t.rest}' if t.rest else '...')
    for a in t.kw_only:
        argument = f'{a.name}:{type_to_dewy(a.type)}'
        args.append(f'@{argument}' if a.place else argument)
    if (
        len(t.pos_or_kw) == 1
        and t.pos_or_kw[0].name is None
        and not t.kw_only
        and t.rest is None
    ):
        signature = args[0]
    else:
        signature = f'({" ".join(args)})'
    parts.append(f'{signature}:>{type_to_dewy(t.ret)}')
    return f'<{"".join(parts)}>'


# ---------------------------------------------------------------------------
# tree repr
# ---------------------------------------------------------------------------

def hir_to_tree_str(node: hir.AST | hir.Param) -> str:
    """Pretty-print an HIR node as an indented tree for debugging/`repr`."""
    space = '    '
    branch = '│   '
    tee = '├── '
    last = '└── '

    lines: list[str] = [_node_label(node)]

    def render(child: hir.AST | hir.Param, prefix: str, edge: str, is_last: bool) -> None:
        connector = last if is_last else tee
        lines.append(f'{prefix}{connector}{edge}: {_node_label(child)}')
        child_prefix = prefix + (space if is_last else branch)
        children = _iter_children(child)
        for i, (e, c) in enumerate(children):
            render(c, child_prefix, e, i == len(children) - 1)

    children = _iter_children(node)
    for i, (edge, child) in enumerate(children):
        render(child, '', edge, i == len(children) - 1)
    return '\n'.join(lines)


def _node_label(node: hir.AST | hir.Param) -> str:
    """Short structural label for a node in the tree dump."""
    # Prefer structural/annotated info over inferred AST.type (except ValueCast).
    if isinstance(node, hir.Void):
        return 'Void'
    if isinstance(node, hir.Suppress):
        return 'Suppress'
    if isinstance(node, hir.Undefined):
        return 'Undefined'
    if isinstance(node, hir.Return):
        return 'Return'
    if isinstance(node, hir.IfArm):
        return 'IfArm'
    if isinstance(node, hir.LoopArm):
        return 'LoopArm'
    if isinstance(node, hir.Flow):
        return f'Flow({len(node.arms)} arms)'
    if isinstance(node, hir.ScopeMetatag):
        return f'ScopeMetatag(${node.name})'
    if isinstance(node, hir.Break):
        if node.label is not None:
            return f'Break(${node.label}, loop_levels={node.loop_levels})'
        return 'Break'
    if isinstance(node, hir.Continue):
        if node.label is not None:
            return f'Continue(${node.label}, loop_levels={node.loop_levels})'
        return 'Continue'
    if isinstance(node, hir.ShortCircuit):
        return f'ShortCircuit({node.op})'
    if isinstance(node, hir.TypeTest):
        operator = 'isnt?' if node.negated else 'is?'
        return f'TypeTest({operator} {type_to_dewy(node.test_type)})'
    if isinstance(node, hir.Declare):
        ann = f':{type_to_dewy(node.annotation)}' if node.annotation is not None else ''
        binding = f' #{node.binding_id}' if node.binding_id is not None else ''
        return f'Declare({node.decltype} {node.name}{ann}){binding}'
    if isinstance(node, hir.Assign):
        return f'Assign({node.op})'
    if isinstance(node, hir.ExpressedIdentifier):
        binding = f' #{node.binding_id}' if node.binding_id is not None else ''
        return f'ExpressedIdentifier({node.name}){binding}'
    if isinstance(node, hir.Place):
        return 'Place(@)'
    if isinstance(node, hir.Bool):
        return f'Bool({node.value})'
    if isinstance(node, hir.RationalConstant):
        return f'Rational({node.numerator}/{node.denominator})'
    if isinstance(node, hir.Integer):
        return f'Integer({_format_integer(node)})'
    if isinstance(node, hir.ArrayLiteral):
        return f'ArrayLiteral({len(node.items)} items)'
    if isinstance(node, hir.ObjectLiteral):
        return f'ObjectLiteral({len(node.fields)} fields)'
    if isinstance(node, hir.MemberAccess):
        return f'MemberAccess(.{node.name})'
    if isinstance(node, hir.MemberAssign):
        return 'MemberAssign'
    if isinstance(node, hir.TypeValue):
        return f'TypeValue({type_alias_value_to_dewy(node.value)})'
    if isinstance(node, hir.ModuleNamespace):
        return f'ModuleNamespace({node.name})'
    if isinstance(node, hir.ArrayLength):
        return 'ArrayLength'
    if isinstance(node, hir.ArrayMethod):
        return f'ArrayMethod({node.name})'
    if isinstance(node, hir.DictLookup):
        return 'DictLookup'
    if isinstance(node, hir.DictMethod):
        return f'DictMethod({node.name})'
    if isinstance(node, hir.DictRemove):
        return 'DictRemove' if node.key is not None else 'DictClear'
    if isinstance(node, hir.DictEntries):
        return f'DictEntries({node.name})'
    if isinstance(node, hir.SetAlgebra):
        return f'SetAlgebra({node.op})'
    if isinstance(node, hir.DictView):
        return f'DictView({node.name})'
    if isinstance(node, hir.DictStore):
        return 'DictStore'
    if isinstance(node, hir.DictContains):
        return 'DictContains'
    if isinstance(node, hir.IteratorExpression):
        return (
            f'IteratorExpression({node.target.name}, '
            f'first={node.first}, step={node.step}, '
            f'last={node.last}, count={node.count})'
        )
    if isinstance(node, hir.MultiIteratorExpression):
        return (
            f'MultiIteratorExpression({len(node.iterators)} leaves, '
            f'repeats={node.repeats_when_exhausted})'
        )
    if isinstance(node, hir.Index):
        return (
            f'Index(constant={node.constant_index})'
            if node.constant_index is not None
            else 'Index(dynamic)'
        )
    if isinstance(node, hir.IndexAssign):
        return 'IndexAssign'
    if isinstance(node, hir.String):
        return f'String({node.content!r})'
    if isinstance(node, hir.InterpolatedString):
        return f'InterpolatedString({len(node.parts)} parts)'
    if isinstance(node, hir.BasedString):
        return f'BasedString({node.prefix}, {node.content.hex()})'
    if isinstance(node, hir.StringLength):
        return 'StringLength'
    if isinstance(node, hir.StringIndex):
        return (
            f'StringIndex(constant={node.constant_index})'
            if node.constant_index is not None
            else 'StringIndex(dynamic)'
        )
    if isinstance(node, hir.StringSlice):
        return 'StringSlice'
    if isinstance(node, hir.StringEqual):
        return 'StringEqual(not=?)' if node.negated else 'StringEqual(=?)'
    if isinstance(node, hir.StringConcat):
        return 'StringConcat(+)'
    if isinstance(node, hir.ValueCast):
        return f'ValueCast(as {type_to_dewy(node.type)})'
    if isinstance(node, hir.RepresentationCast):
        return f'RepresentationCast(as {type_to_dewy(node.type)})'
    if isinstance(node, hir.Transmute):
        return f'Transmute({type_to_dewy(node.type)})'
    if isinstance(node, hir.BoundParam):
        binding = f' #{node.binding_id}' if node.binding_id is not None else ''
        return f'BoundParam({node.name}:{type_to_dewy(node.type)}){binding}'
    if isinstance(node, hir.Param):
        binding = f' #{node.binding_id}' if node.binding_id is not None else ''
        return f'Param({node.name}:{type_to_dewy(node.type)}){binding}'
    if isinstance(node, hir.FunctionLiteral):
        ret = type_to_dewy(node.rettype)
        return f'FunctionLiteral(:>{ret})'
    if isinstance(node, hir.OverloadedFunction):
        return f'OverloadedFunction({len(node.alternates)})'
    if isinstance(node, hir.FunctionCall):
        if (binop := _binop_call(node)) is not None:
            return f'BinOp({binop[0]})'
        if (unary := _prefix_call(node)) is not None:
            return f'Prefix({unary[0]})'
        return 'FunctionCall'
    if isinstance(node, hir.Block):
        scoped = 'scoped' if node.scoped else 'unscoped'
        return f'Block({scoped})'
    if isinstance(node, hir.TypeBlock):
        return 'TypeBlock'
    if isinstance(node, hir.Range):
        bounds = node.bounds if node.bounds is not None else '[]'
        return f'Range({bounds})'
    if isinstance(node, hir.RangeMembership):
        return 'RangeMembership(in?)'
    if isinstance(node, hir.Partial):
        return 'Partial'
    return type(node).__name__


def _iter_children(node: hir.AST | hir.Param) -> list[tuple[str, hir.AST | hir.Param]]:
    """Named child edges for tree dumping; binops/unaries are flattened for readability."""
    if isinstance(node, hir.Return):
        return [('item', node.item)] if node.item is not None else []
    if isinstance(node, hir.Suppress):
        return [('item', node.item)]
    if isinstance(node, (hir.IfArm, hir.LoopArm)):
        return [('condition', node.condition), ('body', node.body)]
    if isinstance(node, hir.Flow):
        out: list[tuple[str, hir.AST | hir.Param]] = [
            (f'arms[{i}]', arm)
            for i, arm in enumerate(node.arms)
        ]
        if node.default is not None:
            out.append(('default', node.default))
        return out
    if isinstance(node, hir.ShortCircuit):
        return [('left', node.left), ('right', node.right)]
    if isinstance(node, hir.TypeTest):
        return [('value', node.value)]
    if isinstance(node, hir.Declare):
        return [('expr', node.expr)]
    if isinstance(node, hir.Assign):
        return [('target', node.target), ('value', node.value)]
    if isinstance(node, hir.Place):
        return [('target', node.target)]
    if isinstance(node, hir.ArrayLiteral):
        return [(f'items[{i}]', item) for i, item in enumerate(node.items)]
    if isinstance(node, hir.ObjectLiteral):
        return [(field.name, field.value) for field in node.fields]
    if isinstance(node, hir.MemberAccess):
        return [('value', node.value)]
    if isinstance(node, hir.MemberAssign):
        return [('target', node.target), ('value', node.value)]
    if isinstance(node, hir.TypeValue):
        return []
    if isinstance(node, hir.ModuleNamespace):
        return []
    if isinstance(node, hir.ArrayLength):
        return [('array', node.array)]
    if isinstance(node, hir.ArrayMethod):
        return [('array', node.array)]
    if isinstance(node, hir.DictLookup):
        return [('keys', node.keys), ('values', node.values), ('key', node.key), *([('default', node.default)] if node.default is not None else [])]
    if isinstance(node, hir.DictMethod):
        return [('dictionary', node.dictionary)]
    if isinstance(node, hir.DictRemove):
        return [('keys', node.keys), *([('values', node.values)] if node.values is not None else []), *([('key', node.key)] if node.key is not None else [])]
    if isinstance(node, hir.DictEntries):
        return [('dictionary', node.dictionary)]
    if isinstance(node, hir.SetAlgebra):
        return [('left', node.left), ('right', node.right)]
    if isinstance(node, hir.DictView):
        return [('dictionary', node.dictionary)]
    if isinstance(node, hir.DictStore):
        return [('keys', node.keys), *([('values', node.values)] if node.values is not None else []), ('key', node.key), *([('value', node.value)] if node.value is not None else [])]
    if isinstance(node, hir.DictContains):
        return [('keys', node.keys), ('key', node.key)]
    if isinstance(node, hir.IteratorExpression):
        return [('target', node.target), ('iterable', node.iterable)]
    if isinstance(node, hir.MultiIteratorExpression):
        return [
            (f'iterators[{index}]', iterator)
            for index, iterator in enumerate(node.iterators)
        ]
    if isinstance(node, hir.Index):
        return [('array', node.array), ('index', node.index)]
    if isinstance(node, hir.IndexAssign):
        return [('target', node.target), ('value', node.value)]
    if isinstance(node, hir.StringLength):
        return [('string', node.string)]
    if isinstance(node, hir.StringIndex):
        return [('string', node.string), ('index', node.index)]
    if isinstance(node, hir.StringSlice):
        return [('string', node.string), ('range', node.range)]
    if isinstance(node, hir.StringEqual):
        return [('left', node.left), ('right', node.right)]
    if isinstance(node, hir.StringConcat):
        return [('left', node.left), ('right', node.right)]
    if isinstance(node, hir.InterpolatedString):
        return [(f'parts[{index}]', part) for index, part in enumerate(node.parts)]
    if isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
        return [('expr', node.expr)]
    if isinstance(node, hir.Transmute):
        return [('expr', node.expr)]
    if isinstance(node, hir.BoundParam):
        return [('value', node.value)]
    if isinstance(node, hir.Param):
        return []
    if isinstance(node, hir.FunctionLiteral):
        out: list[tuple[str, hir.AST | hir.Param]] = []
        for i, p in enumerate(node.pos_or_kw_args):
            out.append((f'pos_or_kw[{i}]', p))
        for i, p in enumerate(node.kw_only_args):
            out.append((f'kw_only[{i}]', p))
        if node.rest_args is not None:
            out.append(('rest', node.rest_args))
        out.append(('body', node.body))
        return out
    if isinstance(node, hir.OverloadedFunction):
        return [(f'alternates[{i}]', a) for i, a in enumerate(node.alternates)]
    if isinstance(node, hir.FunctionCall):
        if (binop := _binop_call(node)) is not None:
            _, left, right = binop
            return [('left', left), ('right', right)]
        if (unary := _prefix_call(node)) is not None:
            _, arg = unary
            return [('item', arg)]
        out = [('func', node.func)]
        for i, a in enumerate(node.pos_args):
            out.append((f'pos_args[{i}]', a))
        for name, a in node.kw_args.items():
            out.append((f'kw.{name}', a))
        return out
    if isinstance(node, hir.Block):
        return [(f'items[{i}]', it) for i, it in enumerate(node.items)]
    if isinstance(node, hir.TypeBlock):
        return [(f'items[{i}]', it) for i, it in enumerate(node.items)]
    if isinstance(node, hir.Range):
        if node.step_pair is not None:
            out = [
                ('step0', node.step_pair[0]),
                ('step1', node.step_pair[1]),
            ]
            if (
                node.right is not None
                and node.right is not node.step_pair[1]
            ):
                out.append(('right', node.right))
            return out
        out = []
        if node.left is not None:
            out.append(('left', node.left))
        if node.right is not None:
            out.append(('right', node.right))
        return out
    if isinstance(node, hir.RangeMembership):
        return [('value', node.value), ('range', node.range)]
    return []


# ---------------------------------------------------------------------------
# Doc algebra + fit-by-width
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Text:
    s: str

@dataclass(frozen=True)
class SoftLine:
    """Space when flat; newline when broken."""

@dataclass(frozen=True)
class HardLine:
    ...

@dataclass(frozen=True)
class Nest:
    n: int
    doc: Doc

@dataclass(frozen=True)
class Group:
    doc: Doc

@dataclass(frozen=True)
class Seq:
    docs: tuple[Doc, ...]

type Doc = Text | SoftLine | HardLine | Nest | Group | Seq

_SOFT = SoftLine()
_HARD = HardLine()


def _text(s: str) -> Doc:
    """Literal text fragment in the Doc algebra."""
    return Text(s)


def _seq(*docs: Doc) -> Doc:
    """Concatenate docs, flattening nested Seq nodes."""
    flat: list[Doc] = []
    for d in docs:
        if isinstance(d, Seq):
            flat.extend(d.docs)
        else:
            flat.append(d)
    if len(flat) == 1:
        return flat[0]
    return Seq(tuple(flat))


def _group(doc: Doc) -> Doc:
    """Mark a region that should stay flat if it fits the line width."""
    return Group(doc)


def _nest(n: int, doc: Doc) -> Doc:
    """Increase indentation for broken lines inside `doc`."""
    return Nest(n, doc)


def _join(sep: Doc, docs: Sequence[Doc]) -> Doc:
    """Join docs with a separator between each pair."""
    if not docs:
        return _text('')
    out: list[Doc] = [docs[0]]
    for d in docs[1:]:
        out.append(sep)
        out.append(d)
    return _seq(*out)


def _render(doc: Doc, width: int) -> str:
    """Layout a Doc to a string, breaking Groups that exceed `width`."""
    # Two-mode Wadler-ish: try each Group flat; if any line would exceed width, break it.
    def fits(remaining: int, docs: list[tuple[int, bool, Doc]]) -> bool:
        rem = remaining
        stack = list(docs)
        while stack:
            indent, flat, d = stack.pop()
            if isinstance(d, Text):
                rem -= len(d.s)
                if rem < 0:
                    return False
            elif isinstance(d, SoftLine):
                if flat:
                    rem -= 1
                    if rem < 0:
                        return False
                else:
                    return True
            elif isinstance(d, HardLine):
                return True
            elif isinstance(d, Nest):
                stack.append((indent + d.n, flat, d.doc))
            elif isinstance(d, Group):
                stack.append((indent, flat, d.doc))
            elif isinstance(d, Seq):
                for child in reversed(d.docs):
                    stack.append((indent, flat, child))
        return True

    out: list[str] = []
    col = 0
    stack: list[tuple[int, bool, Doc]] = [(0, True, doc)]
    while stack:
        indent, flat, d = stack.pop()
        if isinstance(d, Text):
            out.append(d.s)
            col += len(d.s)
        elif isinstance(d, SoftLine):
            if flat:
                out.append(' ')
                col += 1
            else:
                out.append('\n' + ' ' * indent)
                col = indent
        elif isinstance(d, HardLine):
            out.append('\n' + ' ' * indent)
            col = indent
        elif isinstance(d, Nest):
            stack.append((indent + d.n, flat, d.doc))
        elif isinstance(d, Group):
            use_flat = fits(width - col, [(indent, True, d.doc)])
            stack.append((indent, use_flat, d.doc))
        elif isinstance(d, Seq):
            for child in reversed(d.docs):
                stack.append((indent, flat, child))
    return ''.join(out)


# ---------------------------------------------------------------------------
# dunder → infix
# ---------------------------------------------------------------------------

# Display map for known binary dunders (BINOP_DUNDER_MAP may only wire a subset).
_DUNDER_TO_BINOP: dict[str, str] = {
    '__add__': '+',
    '__sub__': '-',
    '__mul__': '*',
    '__truediv__': '/',
    '__floordiv__': '//',
    '__mod__': '%',
    '__pow__': '^',
    '__and__': '&',
    '__or__': '|',
    '__xor__': 'xor',
    '__nand__': 'nand',
    '__nor__': 'nor',
    '__xnor__': 'xnor',
    '__lshift__': '<<',
    '__rshift__': '>>',
    '__eq__': '=?',
    '__ne__': 'not=?',
    '__gt__': '>?',
    '__lt__': '<?',
    '__ge__': '>=?',
    '__le__': '<=?',
}
for _sym, _dunder in builtins.BINOP_DUNDER_MAP.items():
    _DUNDER_TO_BINOP[_dunder] = _sym

_DUNDER_TO_PREFIX: dict[str, str] = {
    '__not__': '~',
    '__unary_add__': '+',
    '__unary_sub__': '-',
    '__unary_multiply__': '*',
    '__unary_divide__': '/',
}
for _sym, _dunder in builtins.UNARY_PREFIX_DUNDER_MAP.items():
    _DUNDER_TO_PREFIX[_dunder] = _sym

def _op_prec(sym: str | type) -> int:
    """Precedence level for an operator symbol (or quantum juxtapose type)."""
    lookup = sym[3:] if isinstance(sym, str) and sym.startswith('not') and sym[3:] in p0.precedence_table else sym
    p = p0.precedence_table[lookup]
    if not isinstance(p, int):
        # quantum prec — take minimum (weakest) for parenthesizing safety
        return min(p.values.keys())
    return p


_AS_PREC = _op_prec('as')
_TRANSMUTE_PREC = _op_prec('transmute')
_AND_PREC = _op_prec('&')
_RANGE_PREC = _op_prec(t2.RangeJuxtapose)
_ARROW_PREC = _op_prec('=>')
_CALL_PREC = _op_prec(t2.CallJuxtapose)
_SEMICOLON_PREC = _op_prec(t2.SemicolonJuxtapose)


def _assoc(prec: int) -> p0.Associativity:
    """Associativity for a given precedence level."""
    return p0.associativity_table[prec]


def _child_min_prec(op_prec: int, side: str) -> int:
    """Minimum precedence a child on `side` ('left'|'right') must have to avoid parens."""
    a = _assoc(op_prec)
    if a is p0.Associativity.left:
        return op_prec if side == 'left' else op_prec + 1
    if a is p0.Associativity.right:
        return op_prec + 1 if side == 'left' else op_prec
    # fail / flat: treat like left for printing
    return op_prec if side == 'left' else op_prec + 1


# ---------------------------------------------------------------------------
# Dewy emit
# ---------------------------------------------------------------------------

def hir_to_dewy(node: hir.AST | hir.Param, *, width: int = 80, indent: int = 4) -> str:
    """Pretty-print an HIR node as Dewy source, wrapping to `width`."""
    doc = _to_doc(node, 0, indent)
    return _render(doc, width)


def _to_doc(node: hir.AST | hir.Param, min_prec: int, indent: int) -> Doc:
    """Convert an HIR node to a Doc, parenthesizing when below `min_prec`."""
    if isinstance(node, hir.Param):
        return _param_doc(node, indent)
    assert isinstance(node, hir.AST)
    if isinstance(node, hir.Void):
        return _text('void')
    if isinstance(node, hir.Suppress):
        item = _to_doc(node.item, _SEMICOLON_PREC + 1, indent)
        keyword_items = (
            hir.Return,
            hir.Declare,
            hir.ScopeMetatag,
            hir.Break,
            hir.Continue,
        )
        needs_group = isinstance(node.item, keyword_items) or (
            isinstance(node.item, hir.Block)
            and not node.item.scoped
            and len(node.item.items) == 1
            and isinstance(node.item.items[0], keyword_items)
        )
        if needs_group:
            item = _seq(_text('('), item, _text(')'))
        return _seq(item, _text(';'))
    if isinstance(node, hir.Undefined):
        return _text('undefined')
    if isinstance(node, hir.RationalConstant):
        return _text(f'{node.numerator}/{node.denominator}')
    if isinstance(node, hir.Integer):
        return _text(_format_integer(node))
    if isinstance(node, hir.Bool):
        return _text('true' if node.value else 'false')
    if isinstance(node, hir.String):
        return _text(repr(node.content))
    if isinstance(node, hir.InterpolatedString):
        parts: list[Doc] = [_text('"')]
        for part in node.parts:
            if isinstance(part, hir.String):
                parts.append(_text(repr(part.content)[1:-1]))
            else:
                parts.extend([
                    _text('{'),
                    _to_doc(part, 0, indent),
                    _text('}'),
                ])
        parts.append(_text('"'))
        return _seq(*parts)
    if isinstance(node, hir.BasedString):
        return _text(f'{node.prefix}"{node.digits}"')
    if isinstance(node, hir.StringLength):
        return _seq(_to_doc(node.string, _CALL_PREC, indent), _text('.length'))
    if isinstance(node, hir.StringIndex):
        return _seq(
            _to_doc(node.string, _CALL_PREC, indent),
            _text('['),
            _to_doc(node.index, 0, indent),
            _text(']'),
        )
    if isinstance(node, hir.StringSlice):
        return _seq(
            _to_doc(node.string, _CALL_PREC, indent),
            _range_doc(node.range, 0, indent),
        )
    if isinstance(node, hir.StringEqual):
        op = 'not=?' if node.negated else '=?'
        return _seq(
            _to_doc(node.left, _op_prec(op), indent),
            _text(f' {op} '),
            _to_doc(node.right, _op_prec(op) + 1, indent),
        )
    if isinstance(node, hir.StringConcat):
        prec = _op_prec('+')
        return _seq(
            _to_doc(node.left, prec, indent),
            _text(' + '),
            _to_doc(node.right, prec + 1, indent),
        )
    if isinstance(node, hir.ArrayLiteral):
        items = [_to_doc(item, 0, indent) for item in node.items]
        return _group(_seq(
            _text('['),
            _nest(indent, _join(_SOFT, items)),
            _text(']'),
        ))
    if isinstance(node, hir.ObjectLiteral):
        items = [
            _seq(
                _text(f'{"const " if not field.mutable else ""}{field.name} = '),
                _to_doc(field.value, 0, indent),
            )
            for field in node.fields
        ]
        return _group(_seq(
            _text('['),
            _nest(indent, _join(_SOFT, items)),
            _text(']'),
        ))
    if isinstance(node, hir.MemberAccess):
        return _seq(
            _to_doc(node.value, _CALL_PREC, indent),
            _text(f'.{node.name}'),
        )
    if isinstance(node, hir.MemberAssign):
        return _seq(
            _to_doc(node.target, 0, indent),
            _text(' = '),
            _to_doc(node.value, 0, indent),
        )
    if isinstance(node, hir.TypeValue):
        return _text(type_alias_value_to_dewy(node.value))
    if isinstance(node, hir.ModuleNamespace):
        return _text(node.name)
    if isinstance(node, hir.ArrayLength):
        return _seq(_to_doc(node.array, _CALL_PREC, indent), _text('.length'))
    if isinstance(node, hir.ArrayMethod):
        return _seq(_to_doc(node.array, _CALL_PREC, indent), _text(f'.{node.name}'))
    if isinstance(node, hir.DictLookup):
        return _seq(_to_doc(node.keys, _CALL_PREC, indent), _text('['), _to_doc(node.key, 0, indent), _text(']'))
    if isinstance(node, hir.DictMethod):
        return _seq(_to_doc(node.dictionary, _CALL_PREC, indent), _text(f'.{node.name}'))
    if isinstance(node, hir.DictEntries):
        return _seq(_to_doc(node.dictionary, _CALL_PREC, indent), _text(f'.{node.name}'))
    if isinstance(node, hir.DictView):
        return _seq(_to_doc(node.dictionary, _CALL_PREC, indent), _text(f'.{node.name}'))
    if isinstance(node, hir.SetAlgebra):
        symbol = {'union': ' | ', 'intersection': ' & ', 'difference': ' - ', 'symmetric': ' xor '}[node.op]
        return _seq(_to_doc(node.left, _CALL_PREC, indent), _text(symbol), _to_doc(node.right, _CALL_PREC, indent))
    if isinstance(node, hir.DictRemove):
        if node.key is None:
            return _seq(_to_doc(node.keys, _CALL_PREC, indent), _text('.clear'))
        return _seq(_to_doc(node.keys, _CALL_PREC, indent), _text('.pop('), _to_doc(node.key, 0, indent), _text(')'))
    if isinstance(node, hir.DictStore):
        if node.value is None:
            return _seq(_to_doc(node.keys, _CALL_PREC, indent), _text('.add('), _to_doc(node.key, 0, indent), _text(')'))
        return _seq(
            _to_doc(node.keys, _CALL_PREC, indent), _text('['), _to_doc(node.key, 0, indent),
            _text('] = '), _to_doc(node.value, 0, indent),
        )
    if isinstance(node, hir.DictContains):
        return _seq(_to_doc(node.key, _CALL_PREC, indent), _text(' in? '), _to_doc(node.keys, _CALL_PREC, indent))
    if isinstance(node, hir.IteratorExpression):
        return _seq(
            _to_doc(node.target, 0, indent),
            _text(' in '),
            _to_doc(node.iterable, 0, indent),
        )
    if isinstance(node, hir.MultiIteratorExpression):
        stack: list[Doc] = []
        for token in node.formula:
            if isinstance(token, int):
                stack.append(_to_doc(node.iterators[token], 0, indent))
                continue
            right = stack.pop()
            left = stack.pop()
            stack.append(
                _seq(_text('('), left, _text(f' {token} '), right, _text(')'))
            )
        return stack[0]
    if isinstance(node, hir.Index):
        return _seq(
            _to_doc(node.array, _CALL_PREC, indent),
            _text('['),
            _to_doc(node.index, 0, indent),
            _text(']'),
        )
    if isinstance(node, hir.ExpressedIdentifier):
        return _text(node.name)
    if isinstance(node, hir.Place):
        return _seq(_text('@'), _to_doc(node.target, 0, indent))
    if isinstance(node, hir.Return):
        if node.item is None:
            return _text('return')
        return _seq(_text('return '), _to_doc(node.item, 0, indent))
    if isinstance(node, hir.Flow):
        return _flow_doc(node, min_prec, indent)
    if isinstance(node, hir.ScopeMetatag):
        return _text(f'${node.name}')
    if isinstance(node, hir.Break):
        suffix = f' ${node.label}' if node.label is not None else ''
        return _text(f'break{suffix}')
    if isinstance(node, hir.Continue):
        suffix = f' ${node.label}' if node.label is not None else ''
        return _text(f'continue{suffix}')
    if isinstance(node, hir.ShortCircuit):
        return _short_circuit_doc(node, min_prec, indent)
    if isinstance(node, hir.TypeTest):
        operator = 'isnt?' if node.negated else 'is?'
        return _seq(
            _to_doc(node.value, 0, indent),
            _text(f' {operator} {type_to_dewy(node.test_type)}'),
        )
    if isinstance(node, (hir.IfArm, hir.LoopArm)):
        raise TypeError(f'{type(node).__name__} can only be rendered inside Flow')
    if isinstance(node, hir.Declare):
        # No Nest around the RHS: a Nest would still apply to HardLines inside a
        # block body even when the SoftLine after `=` stays flat, over-indenting.
        ann = f':{type_to_dewy(node.annotation)}' if node.annotation is not None else ''
        return _group(_seq(
            _text(f'{node.decltype} {node.name}{ann} ='),
            _seq(_SOFT, _to_doc(node.expr, 0, indent)),
        ))
    if isinstance(node, hir.Assign):
        return _group(_seq(
            _to_doc(node.target, 0, indent),
            _text(f' {node.op}'),
            _seq(_SOFT, _to_doc(node.value, 0, indent)),
        ))
    if isinstance(node, hir.IndexAssign):
        return _group(_seq(
            _to_doc(node.target, 0, indent),
            _text(' ='),
            _seq(_SOFT, _to_doc(node.value, 0, indent)),
        ))
    if isinstance(node, hir.ValueCast):
        # `ValueCast.type` is the cast target (the value's expressed type).
        inner = _seq(
            _to_doc(node.expr, _AS_PREC + 1, indent),
            _text(' as '),
            _text(type_to_dewy(node.type)),
        )
        if _AS_PREC < min_prec:
            return _seq(_text('('), inner, _text(')'))
        return inner
    if isinstance(node, hir.RepresentationCast):
        inner = _seq(
            _to_doc(node.expr, _AS_PREC + 1, indent),
            _text(' as '),
            _text(type_to_dewy(node.type)),
        )
        if _AS_PREC < min_prec:
            return _seq(_text('('), inner, _text(')'))
        return inner
    if isinstance(node, hir.Transmute):
        inner = _seq(
            _to_doc(node.expr, _TRANSMUTE_PREC + 1, indent),
            _text(' transmute '),
            _text(type_to_dewy(node.type)),
        )
        if _TRANSMUTE_PREC < min_prec:
            return _seq(_text('('), inner, _text(')'))
        return inner
    if isinstance(node, hir.FunctionCall):
        return _call_doc(node, min_prec, indent)
    if isinstance(node, hir.FunctionLiteral):
        return _function_literal_doc(node, min_prec, indent)
    if isinstance(node, hir.OverloadedFunction):
        return _overload_doc(node, min_prec, indent)
    if isinstance(node, hir.Block):
        return _block_doc(node, min_prec, indent)
    if isinstance(node, hir.TypeBlock):
        items = [_to_doc(it, 0, indent) for it in node.items]
        return _group(_seq(
            _text('<'),
            _nest(indent, _seq(_SOFT, _join(_SOFT, items))),
            _SOFT,
            _text('>'),
        ))
    if isinstance(node, hir.Range):
        return _range_doc(node, min_prec, indent)
    if isinstance(node, hir.RangeMembership):
        return _group(_seq(
            _to_doc(node.value, 0, indent),
            _text(' in? '),
            _to_doc(node.range, 0, indent),
        ))
    if isinstance(node, hir.Partial):
        return _text('<partial>')
    raise TypeError(f'unhandled HIR node in printer: {type(node).__name__}')


def _param_doc(p: hir.Param, indent: int) -> Doc:
    """Render a parameter as `name:type` or `name:type=default`."""
    base = _text(f'{p.name}:{type_to_dewy(p.type)}')
    if p.place:
        base = _seq(_text('@'), base)
    if isinstance(p, hir.BoundParam):
        return _seq(base, _text('='), _to_doc(p.value, 0, indent))
    return base


def _format_integer(node: hir.Integer) -> str:
    """Format an integer literal with its original base prefix."""
    if node.prefix == t0.base10:
        return str(node.value)
    digits, casefold, _extra = t0.BASE_SPECS[node.prefix]
    radix = len(digits)
    if node.value == 0:
        body = digits[0]
    else:
        n = node.value
        chars: list[str] = []
        while n:
            n, r = divmod(n, radix)
            chars.append(digits[r])
        body = ''.join(reversed(chars))
        if casefold:
            body = body.lower()
    return f'{node.prefix}{body}'


def _binop_call(node: hir.FunctionCall) -> tuple[str, hir.AST, hir.AST] | None:
    """If this call is a binary dunder, return `(op_symbol, left, right)`."""
    if len(node.pos_args) != 2 or node.kw_args:
        return None
    if not isinstance(node.func, hir.ExpressedIdentifier):
        return None
    sym = _DUNDER_TO_BINOP.get(node.func.name)
    if sym is None:
        return None
    return sym, node.pos_args[0], node.pos_args[1]


def _prefix_call(node: hir.FunctionCall) -> tuple[str, hir.AST] | None:
    """If this call is a unary prefix dunder, return `(op_symbol, arg)`."""
    if len(node.pos_args) != 1 or node.kw_args:
        return None
    if not isinstance(node.func, hir.ExpressedIdentifier):
        return None
    sym = _DUNDER_TO_PREFIX.get(node.func.name)
    if sym is None:
        return None
    return sym, node.pos_args[0]


def _call_doc(node: hir.FunctionCall, min_prec: int, indent: int) -> Doc:
    """Render a call as infix/prefix when possible, otherwise as `f(args)`."""
    if (binop := _binop_call(node)) is not None:
        sym, left, right = binop
        prec = _op_prec(sym)
        doc = _seq(
            _to_doc(left, _child_min_prec(prec, 'left'), indent),
            _text(f' {sym} '),
            _to_doc(right, _child_min_prec(prec, 'right'), indent),
        )
        if prec < min_prec:
            return _seq(_text('('), doc, _text(')'))
        return doc
    if (unary := _prefix_call(node)) is not None:
        sym, arg = unary
        prec = _op_prec(sym)
        prefix = f'{sym} ' if sym.isalpha() else sym
        doc = _seq(_text(prefix), _to_doc(arg, prec, indent))
        if prec < min_prec:
            return _seq(_text('('), doc, _text(')'))
        return doc

    # Normal call: f(a b kw=x)
    args: list[Doc] = [_to_doc(a, 0, indent) for a in node.pos_args]
    for name, a in node.kw_args.items():
        args.append(_seq(_text(f'{name}='), _to_doc(a, 0, indent)))
    arg_doc = _group(_join(_SOFT, args)) if args else _text('')
    call = _seq(_to_doc(node.func, _CALL_PREC, indent), _text('('), arg_doc, _text(')'))
    if _CALL_PREC < min_prec:
        return _seq(_text('('), call, _text(')'))
    return call


def _short_circuit_doc(node: hir.ShortCircuit, min_prec: int, indent: int) -> Doc:
    """Render a lazy boolean logical operator with normal operator precedence."""
    prec = _op_prec(node.op)
    doc = _seq(
        _to_doc(node.left, _child_min_prec(prec, 'left'), indent),
        _text(f' {node.op} '),
        _to_doc(node.right, _child_min_prec(prec, 'right'), indent),
    )
    if prec < min_prec:
        return _seq(_text('('), doc, _text(')'))
    return doc


def _flow_doc(node: hir.Flow, min_prec: int, indent: int) -> Doc:
    """Render an ordered structured flow chain."""
    docs: list[Doc] = []
    for i, arm in enumerate(node.arms):
        if i:
            docs.append(_text(' else '))
        keyword = 'if' if isinstance(arm, hir.IfArm) else 'loop'
        docs.extend([
            _text(f'{keyword} '),
            _to_doc(arm.condition, 0, indent),
            _text(' '),
            _to_doc(arm.body, 0, indent),
        ])
    if node.default is not None:
        docs.extend([_text(' else '), _to_doc(node.default, 0, indent)])
    doc = _seq(*docs)
    if min_prec > 0:
        return _seq(_text('('), doc, _text(')'))
    return doc


def _function_literal_doc(node: hir.FunctionLiteral, min_prec: int, indent: int) -> Doc:
    """Render a function literal as `(args):>ret => body`."""
    args: list[Doc] = [
        _seq(_text('<'), _param_doc(p, indent), _text('>'))
        if p.position_only
        else _param_doc(p, indent)
        for p in node.pos_or_kw_args
    ]
    if node.rest_args is not None or node.kw_only_args:
        if node.rest_args is not None:
            args.append(_seq(_text('...'), _param_doc(node.rest_args, indent)))
        else:
            args.append(_text('...'))
    args.extend(_param_doc(p, indent) for p in node.kw_only_args)
    sig = _seq(
        _text('('),
        _group(_join(_SOFT, args)) if args else _text(''),
        _text('):>'),
        _text(type_to_dewy(node.rettype)),
    )
    body = _to_doc(node.body, 0, indent)
    # Block bodies already own brace indentation; don't Nest/`SoftLine` around them.
    if isinstance(node.body, hir.Block):
        doc = _seq(sig, _text(' => '), body)
    else:
        doc = _group(_seq(sig, _text(' =>'), _nest(indent, _seq(_SOFT, body))))
    if _ARROW_PREC < min_prec:
        return _seq(_text('('), doc, _text(')'))
    return doc


def _overload_doc(node: hir.OverloadedFunction, min_prec: int, indent: int) -> Doc:
    """Render an overloaded function as a chain of `a & b & ...` alternates."""
    if not node.alternates:
        return _text('()')
    prec = _AND_PREC
    parts = [_to_doc(a, _child_min_prec(prec, 'left' if i == 0 else 'right'), indent)
             for i, a in enumerate(node.alternates)]
    # Chain: a & b & c — each subsequent needs right-child prec relative to &
    docs: list[Doc] = [parts[0]]
    for p in parts[1:]:
        docs.append(_text(' & '))
        docs.append(p)
    doc = _seq(*docs)
    if prec < min_prec:
        return _seq(_text('('), doc, _text(')'))
    return doc


def _block_doc(node: hir.Block, min_prec: int, indent: int) -> Doc:
    """Render a block as `{...}` / `(...)`, omitting delimiters for a single unscoped item."""
    items = [it for it in node.items if not isinstance(it, hir.Void)]
    open_b, close_b = ('{', '}') if node.scoped else ('(', ')')
    if not items:
        return _text(f'{open_b}{close_b}')
    if len(items) == 1 and not node.scoped:
        # Single unscoped item: omit delimiters when precedence allows
        return _to_doc(items[0], min_prec, indent)
    body = _join(_HARD, [_to_doc(it, 0, indent) for it in items])
    return _seq(
        _text(open_b),
        _nest(indent, _seq(_HARD, body)),
        _HARD,
        _text(close_b),
    )


def _range_doc(node: hir.Range, min_prec: int, indent: int) -> Doc:
    """Render a range as `left..right` with optional step and bounds markers."""
    if node.step_pair is not None:
        s0 = _to_doc(node.step_pair[0], 0, indent)
        s1 = _to_doc(node.step_pair[1], 0, indent)
        if node.left is not None:
            right = (
                _to_doc(node.right, _RANGE_PREC + 1, indent)
                if node.right is not None
                else _text('')
            )
            core = _seq(s0, _text(','), s1, _text('..'), right)
        else:
            core = _seq(_text('..'), s0, _text(','), s1)
    else:
        left = (
            _to_doc(node.left, _RANGE_PREC + 1, indent)
            if node.left is not None
            else _text('')
        )
        right = (
            _to_doc(node.right, _RANGE_PREC + 1, indent)
            if node.right is not None
            else _text('')
        )
        core = _seq(left, _text('..'), right)
    if node.bounds is not None and node.bounds != '[]':
        # wrap with bound markers — Dewy uses bracket forms around the range
        lo, hi = node.bounds[0], node.bounds[1]
        core = _seq(_text(lo), core, _text(hi))
    if _RANGE_PREC < min_prec:
        return _seq(_text('('), core, _text(')'))
    return core
