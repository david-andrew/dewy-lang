"""HIR tree dump (`repr`) and Dewy pretty-printer (`str`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..parser import p0, t0, t2
from . import builtins, hir, ty

# ---------------------------------------------------------------------------
# type → Dewy
# ---------------------------------------------------------------------------

def type_to_dewy(t: ty.Type) -> str:
    if isinstance(t, str):
        return t
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
    if isinstance(t, ty.FunctionType):
        return _function_type_to_dewy(t)
    if isinstance(t, ty.OverloadType):
        return ' & '.join(_type_atom_parens(m) for m in t.methods)
    if isinstance(t, ty.SequenceType):
        return f'<{" ".join(type_to_dewy(x) for x in t.items)}>'
    raise TypeError(f'unexpected type for type_to_dewy: {t!r}')


def _type_atom_parens(t: ty.Type) -> str:
    s = type_to_dewy(t)
    if isinstance(t, (ty.TypeAnd, ty.TypeOr, ty.OverloadType)):
        return f'({s})'
    return s


def _function_type_to_dewy(t: ty.FunctionType) -> str:
    parts: list[str] = []
    if t.type_params:
        gens = ' '.join(
            p.name if p.bound == ty.TOP_TYPE else f'{p.name} of {type_to_dewy(p.bound)}'
            for p in t.type_params
        )
        parts.append(f'<{gens}>')
    args: list[str] = []
    for a in t.pos_or_kw:
        args.append(f'{a.name}:{type_to_dewy(a.type)}')
    if t.rest is not None or t.kw_only:
        args.append(f'...{t.rest}' if t.rest else '...')
    for a in t.kw_only:
        args.append(f'{a.name}:{type_to_dewy(a.type)}')
    parts.append(f'({" ".join(args)}):>{type_to_dewy(t.ret)}')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# tree repr
# ---------------------------------------------------------------------------

def hir_to_tree_str(node: hir.AST | hir.Param) -> str:
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
    # Prefer structural/annotated info over inferred AST.type (except ValueCast).
    if isinstance(node, hir.Void):
        return 'Void'
    if isinstance(node, hir.Return):
        return 'Return'
    if isinstance(node, hir.Declare):
        ann = f':{type_to_dewy(node.annotation)}' if node.annotation is not None else ''
        return f'Declare({node.decltype} {node.name}{ann})'
    if isinstance(node, hir.ExpressedIdentifier):
        return f'ExpressedIdentifier({node.name})'
    if isinstance(node, hir.Bool):
        return f'Bool({node.value})'
    if isinstance(node, hir.Integer):
        return f'Integer({_format_integer(node)})'
    if isinstance(node, hir.String):
        return f'String({node.content!r})'
    if isinstance(node, hir.ValueCast):
        return f'ValueCast(as {type_to_dewy(node.type)})'
    if isinstance(node, hir.BoundParam):
        return f'BoundParam({node.name}:{type_to_dewy(node.type)})'
    if isinstance(node, hir.Param):
        return f'Param({node.name}:{type_to_dewy(node.type)})'
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
    if isinstance(node, hir.Partial):
        return 'Partial'
    return type(node).__name__


def _iter_children(node: hir.AST | hir.Param) -> list[tuple[str, hir.AST | hir.Param]]:
    if isinstance(node, hir.Return):
        return [('item', node.item)] if node.item is not None else []
    if isinstance(node, hir.Declare):
        return [('expr', node.expr)]
    if isinstance(node, hir.ValueCast):
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
        out = []
        if node.left is not None:
            out.append(('left', node.left))
        if node.right is not None:
            out.append(('right', node.right))
        if node.step_pair is not None:
            out.append(('step0', node.step_pair[0]))
            out.append(('step1', node.step_pair[1]))
        return out
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
    return Text(s)


def _seq(*docs: Doc) -> Doc:
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
    return Group(doc)


def _nest(n: int, doc: Doc) -> Doc:
    return Nest(n, doc)


def _join(sep: Doc, docs: Sequence[Doc]) -> Doc:
    if not docs:
        return _text('')
    out: list[Doc] = [docs[0]]
    for d in docs[1:]:
        out.append(sep)
        out.append(d)
    return _seq(*out)


def _render(doc: Doc, width: int) -> str:
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
    p = p0.precedence_table[sym]
    if not isinstance(p, int):
        # quantum prec — take minimum (weakest) for parenthesizing safety
        return min(p.values.keys())
    return p


_AS_PREC = _op_prec('as')
_AND_PREC = _op_prec('&')
_RANGE_PREC = _op_prec(t2.RangeJuxtapose)
_ARROW_PREC = _op_prec('=>')
_CALL_PREC = _op_prec(t2.CallJuxtapose)


def _assoc(prec: int) -> p0.Associativity:
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
    doc = _to_doc(node, 0, indent)
    return _render(doc, width)


def _to_doc(node: hir.AST | hir.Param, min_prec: int, indent: int) -> Doc:
    if isinstance(node, hir.Param):
        return _param_doc(node, indent)
    assert isinstance(node, hir.AST)
    if isinstance(node, hir.Void):
        return _text('')
    if isinstance(node, hir.Integer):
        return _text(_format_integer(node))
    if isinstance(node, hir.Bool):
        return _text('true' if node.value else 'false')
    if isinstance(node, hir.String):
        return _text(repr(node.content))
    if isinstance(node, hir.ExpressedIdentifier):
        return _text(node.name)
    if isinstance(node, hir.Return):
        if node.item is None:
            return _text('return')
        return _seq(_text('return '), _to_doc(node.item, 0, indent))
    if isinstance(node, hir.Declare):
        # No Nest around the RHS: a Nest would still apply to HardLines inside a
        # block body even when the SoftLine after `=` stays flat, over-indenting.
        ann = f':{type_to_dewy(node.annotation)}' if node.annotation is not None else ''
        return _group(_seq(
            _text(f'{node.decltype} {node.name}{ann} ='),
            _seq(_SOFT, _to_doc(node.expr, 0, indent)),
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
    if isinstance(node, hir.Partial):
        return _text('<partial>')
    raise TypeError(f'unhandled HIR node in printer: {type(node).__name__}')


def _param_doc(p: hir.Param, indent: int) -> Doc:
    base = _text(f'{p.name}:{type_to_dewy(p.type)}')
    if isinstance(p, hir.BoundParam):
        return _seq(base, _text('='), _to_doc(p.value, 0, indent))
    return base


def _format_integer(node: hir.Integer) -> str:
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
    if len(node.pos_args) != 2 or node.kw_args:
        return None
    if not isinstance(node.func, hir.ExpressedIdentifier):
        return None
    sym = _DUNDER_TO_BINOP.get(node.func.name)
    if sym is None:
        return None
    return sym, node.pos_args[0], node.pos_args[1]


def _prefix_call(node: hir.FunctionCall) -> tuple[str, hir.AST] | None:
    if len(node.pos_args) != 1 or node.kw_args:
        return None
    if not isinstance(node.func, hir.ExpressedIdentifier):
        return None
    sym = _DUNDER_TO_PREFIX.get(node.func.name)
    if sym is None:
        return None
    return sym, node.pos_args[0]


def _call_doc(node: hir.FunctionCall, min_prec: int, indent: int) -> Doc:
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
        doc = _seq(_text(sym), _to_doc(arg, prec, indent))
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


def _function_literal_doc(node: hir.FunctionLiteral, min_prec: int, indent: int) -> Doc:
    args: list[Doc] = [_param_doc(p, indent) for p in node.pos_or_kw_args]
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
    left = _to_doc(node.left, _RANGE_PREC + 1, indent) if node.left is not None else _text('')
    right = _to_doc(node.right, _RANGE_PREC + 1, indent) if node.right is not None else _text('')
    core = _seq(left, _text('..'), right)
    if node.step_pair is not None:
        s0 = _to_doc(node.step_pair[0], 0, indent)
        s1 = _to_doc(node.step_pair[1], 0, indent)
        core = _seq(core, _text(','), s0, _text('..'), s1)
    if node.bounds is not None and node.bounds != '[]':
        # wrap with bound markers — Dewy uses bracket forms around the range
        lo, hi = node.bounds[0], node.bounds[1]
        core = _seq(_text(lo), core, _text(hi))
    if _RANGE_PREC < min_prec:
        return _seq(_text('('), core, _text(')'))
    return core
