"""Typed, bounded Dewy programs and an independent subset interpreter (the oracle).

The generator writes the surface of docs/LANGUAGE.md, not the compiler's Jo
input. `Machine` executes the same tree in Python and supplies the expected
output. It shares nothing with the compiler: wherever Dewy promises an
independent value (let, assignment, arguments, captures, collection inserts)
the oracle makes an eager deep copy instead of copy-on-write.

Integers are mostly explicit `int64`/`uint64`, which wrap; the `checked` feature
adds unannotated `int`, whose overflow is a checked failure (exit 101, or a
compile-time error when provable). Floats are `float64`. `@fn` handles and
units are deliberately absent while they change.

Adding a feature:
- a node class with `render` (its Dewy text) and `eval` (its semantics);
- a generator block `Generator.block_<feature>`, listed in FEATURES;
- expression productions in `Generator.expr_<kind>` when it yields values.
Variants (identity copy, reordering, outlining, loop→comprehension) and the
shrinker work on any node through `fields`, so they need no per-feature code.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from typing import Any

# Types ------------------------------------------------------------------------

@dataclass(frozen=True)
class Ty:
    kind: str
    args: tuple = ()
    name: str = ''

    def __str__(self):
        k, a = self.kind, self.args
        if k == 'array':
            return f'array<{a[0]}>'
        if k == 'dict':
            return f'dict<{a[0]} {a[1]}>'
        if k == 'set':
            return f'set<{a[0]}>'
        if k == 'opt':
            return f'{a[0]}?'
        if k == 'union':
            return '|'.join(map(str, a))
        if k == 'rec':
            return self.name or '[' + ' '.join(f'{n}:{t}' for n, t in a) + ']'
        return k

    def field(self, name):
        return dict(self.args)[name]


I, U, F, B, S = (Ty(k) for k in ('int64', 'uint64', 'float64', 'bool', 'string'))
INT = Ty('int')  # checked mathematical integer: unannotated literals; overflow is a failure
VOID, RANGE, HIDDEN = Ty('void'), Ty('range'), Ty('hidden')
FN = Ty('fn', (I,), I)  # (int64):>int64 closures with private state
AI, AS, AF = Ty('array', (I,)), Ty('array', (S,)), Ty('array', (F,))
AAI = Ty('array', (AI,))
DII, DSA = Ty('dict', (I, I)), Ty('dict', (S, AI))
SI, SS = Ty('set', (I,)), Ty('set', (S,))
OI, OS = Ty('opt', (I,)), Ty('opt', (S,))
UIS = Ty('union', (I, S))
ITEM = Ty('rec', (('id', I), ('tags', AI), ('label', S)), 'Item')
CELL = Ty('rec', (('value', I), ('xs', AI)))
PAIR = Ty('rec', (('left', F), ('right', I)))
RECORDS = (ITEM, CELL, PAIR)
BAD = Ty('rec', (('code', I),), 'Bad')  # `Bad:type=type of error & [code:int64]`
RESULT = Ty('union', (I, BAD))
INTS = (I, U, INT)
SCALARS = (I, U, F, B, S)
AITEM = Ty('array', (ITEM,))
VALUE_TYPES = (I, U, F, B, S, AI, AS, AF, AAI, DII, DSA, SI, SS, OI, OS, UIS, ITEM, CELL, PAIR, AITEM)
MUTATING = {'push', 'pop', 'remove'}

WORDS = ('dewy', 'café', 'λx', '🙂', 'a b', 'q"t', 'back\\slash', '{brace}', 'line\nnext',
         'tab\there', '', 'Z', 'ok', 'ünï', 'x=1')


# Nodes ------------------------------------------------------------------------

class Node:
    def render(self, typed=False):
        raise NotImplementedError


class Expr(Node):
    ty: Ty


class Stmt(Node):
    pass


def render(node, typed=False):
    return node.render(typed)


def atom(node):
    text = render(node)
    return text if isinstance(node, (Var, Field, Index, Call, Method)) else f'({text})'


def escape(text: str) -> str:
    table = {'\\': '\\\\', '"': '\\"', '{': '\\{', '}': '\\}', '\n': '\\n', '\t': '\\t'}
    return ''.join(table.get(c, c) for c in text)


def quote(text: str) -> str:
    return '"' + escape(text) + '"'


def float_literal(value: float) -> str:
    text = repr(value)
    return text if ('e' not in text and 'inf' not in text) else f'{value:.17g}'


@dataclass(frozen=True)
class Lit(Expr):
    ty: Ty
    value: Any

    def render(self, typed=False):
        v, k = self.value, self.ty.kind
        if v is None:
            return 'none'
        if k == 'bool':
            return 'true' if v else 'false'
        if k == 'string':
            return quote(v)
        if k == 'int64' and v in (-2 ** 63, 2 ** 63 - 1):
            return 'int64.min' if v < 0 else 'int64.max'
        if k == 'uint64' and v == 2 ** 64 - 1:
            return 'uint64.max'
        text = float_literal(v) if k == 'float64' else str(v)
        if typed or k == 'int':
            return f'({text})' if text.startswith('-') else text
        return f'{k}({text})'

    def eval(self, m, env):
        return self.value


@dataclass(frozen=True)
class Var(Expr):
    ty: Ty
    name: str

    def render(self, typed=False):
        # A function value is a handle: a bare function name would call it.
        return f'@{self.name}' if self.ty == FN else self.name

    def eval(self, m, env):
        return env.get(self.name, m)


@dataclass(frozen=True)
class Unary(Expr):
    ty: Ty
    op: str
    x: Expr

    def render(self, typed=False):
        return f'({self.op}{" " if self.op == "not" else ""}{render(self.x)})'

    def eval(self, m, env):
        x = m.eval(self.x, env)
        return (not x) if self.op == 'not' else wrap(-x, self.ty)


def declared(e):
    return isinstance(e, (Var, Field, Index, Call, Length, Method, Conv, Unary, Bin))


def ordered(op, x, y):
    return {'<?': x < y, '>?': x > y, '<=?': x <= y, '>=?': x >= y}[op]


@dataclass(frozen=True)
class Bin(Expr):
    ty: Ty
    op: str
    left: Expr
    right: Expr

    def render(self, typed=False):
        # A literal beside an operand with a declared type adopts that type; anything
        # else renders without context (its literals spell their type).
        left = render(self.left, isinstance(self.left, Lit) and declared(self.right))
        right = render(self.right, isinstance(self.right, Lit) and declared(self.left))
        return f'({left} {self.op} {right})'

    def eval(self, m, env):
        op = self.op
        x = m.eval(self.left, env)
        if op in ('and', 'or') and self.ty == B:
            if op == 'and':
                return x and m.eval(self.right, env)
            return x or m.eval(self.right, env)
        if op == '??':
            return x if x is not None else m.eval(self.right, env)
        y = m.eval(self.right, env)
        if op == '=?':
            return equal(x, y)
        if op == 'not=?':
            return not equal(x, y)
        if op in ('<?', '>?', '<=?', '>=?'):
            return ordered(op, x, y)
        if op == 'in?':
            return x in (y.items if isinstance(y, DSet) else y)
        if self.ty == S:
            return x + y
        if self.ty.kind == 'set':
            if op == '|':
                return DSet([*x.items, *y.items])
            if op == '&':
                return DSet(k for k in x.items if k in y.items)
            return DSet(k for k in x.items if k not in y.items)
        if self.ty == F:
            if op == '/' and y == 0:
                raise InvalidProgram('float division by zero')
            return {'+': x + y, '-': x - y, '*': x * y, '/': x / y if y else 0.0}[op]
        if op in ('//', '%') and y == 0:
            raise InvalidProgram('integer division by zero')
        if op == '^' and not 0 <= y <= 8:
            raise InvalidProgram('power exponent')
        if op in ('<<', '>>') and not 0 <= y < 64:
            raise InvalidProgram('shift count')
        value = {'+': lambda: x + y, '-': lambda: x - y, '*': lambda: x * y,
                 '//': lambda: x // y, '%': lambda: x % y, '^': lambda: x ** y,
                 '<<': lambda: x << y, '>>': lambda: x >> y, 'and': lambda: x & y,
                 'or': lambda: x | y, 'xor': lambda: x ^ y}[op]()
        return wrap(value, self.ty)


@dataclass(frozen=True)
class Cond(Expr):
    ty: Ty
    test: Expr
    then: Expr
    other: Expr

    def render(self, typed=False):
        return f'(if {render(self.test)} {render(self.then, typed)} else {render(self.other, typed)})'

    def eval(self, m, env):
        return m.eval(self.then if m.eval(self.test, env) else self.other, env)


@dataclass(frozen=True)
class MatchLit(Expr):
    ty: Ty
    subject: Expr
    arms: tuple  # ((Lit, Expr), ...)
    default: Expr

    def render(self, typed=False):
        arms = ' '.join(f'<{k.value}>=>{render(v, typed)}' for k, v in self.arms)
        return f'(match {render(self.subject)} {{{arms} _=>{render(self.default, typed)}}})'

    def eval(self, m, env):
        subject = m.eval(self.subject, env)
        for key, value in self.arms:
            if key.value == subject:
                return m.eval(value, env)
        return m.eval(self.default, env)


@dataclass(frozen=True)
class MatchOpt(Expr):
    """`match o {n:T=>some <none>=>absent}`; `n` is bound in `some`."""
    ty: Ty
    subject: Expr
    bind: str
    some: Expr
    absent: Expr

    def render(self, typed=False):
        inner = self.subject.ty.args[0]
        return (f'(match {render(self.subject)} {{{self.bind}:{inner}=>{render(self.some, typed)} '
                f'<none>=>{render(self.absent, typed)}}})')

    def eval(self, m, env):
        value = m.eval(self.subject, env)
        if value is None:
            return m.eval(self.absent, env)
        return m.eval(self.some, Scope({self.bind: copy.deepcopy(value)}, env))


@dataclass(frozen=True)
class MatchUnion(Expr):
    """`match u {n:int64=>a t:string=>b}` over int64|string."""
    ty: Ty
    subject: Expr
    arms: tuple  # ((name, Ty, Expr), ...)

    def render(self, typed=False):
        arms = ' '.join(f'{n}:{t}=>{render(e, typed)}' for n, t, e in self.arms)
        return f'(match {render(self.subject)} {{{arms}}})'

    def eval(self, m, env):
        value = m.eval(self.subject, env)
        for name, ty, body in self.arms:
            if member(value, ty):
                return m.eval(body, Scope({name: copy.deepcopy(value)}, env))
        raise InvalidProgram('non-exhaustive union match')


def member(value, ty):
    if ty == BAD:
        return isinstance(value, Rec) and value.name == 'Bad'
    if ty == S:
        return isinstance(value, str)
    if ty == I:
        return isinstance(value, int) and not isinstance(value, bool)
    if ty.kind == 'none':
        return value is None
    raise InvalidProgram(f'type test {ty}')


@dataclass(frozen=True)
class Is(Expr):
    ty: Ty
    x: Expr
    test: str  # 'none', 'int64' or 'string'
    negate: bool = False

    def render(self, typed=False):
        return f'({render(self.x)} {"isnt?" if self.negate else "is?"} {self.test})'

    def eval(self, m, env):
        value = m.eval(self.x, env)
        found = member(value, {'none': Ty('none'), 'int64': I, 'string': S, 'Bad': BAD, 'error': BAD}[self.test])
        return found != self.negate


@dataclass(frozen=True)
class ArrayLit(Expr):
    ty: Ty
    items: tuple

    def render(self, typed=False):
        return '[' + ' '.join(render(x, typed) for x in self.items) + ']'

    def eval(self, m, env):
        return [copy.deepcopy(m.eval(x, env)) for x in self.items]


@dataclass(frozen=True)
class RecLit(Expr):
    ty: Ty
    items: tuple  # ((field, Expr), ...) in written order
    positional: bool = False

    def render(self, typed=False):
        typed = typed or bool(self.ty.name)
        if self.positional:
            return self.ty.name + '[' + ' '.join(render(e, typed) for _, e in self.items) + ']'
        body = ' '.join(f'{n}={render(e, typed)}' for n, e in self.items)
        return f'{self.ty.name}[{body}]'

    def eval(self, m, env):
        values = {n: copy.deepcopy(m.eval(e, env)) for n, e in self.items}
        return Rec(self.ty.name, {n: values[n] for n, _ in self.ty.args})


@dataclass(frozen=True)
class DictLit(Expr):
    ty: Ty
    items: tuple  # ((key, value), ...)

    def render(self, typed=False):
        return '[' + ' '.join(f'{render(k, typed)}->{render(v, typed)}' for k, v in self.items) + ']'

    def eval(self, m, env):
        result = {}
        for k, v in self.items:
            key = m.eval(k, env)
            result[key] = copy.deepcopy(m.eval(v, env))
        return result


@dataclass(frozen=True)
class SetLit(Expr):
    ty: Ty
    items: tuple

    def render(self, typed=False):
        return 'set[' + ' '.join(render(x, typed) for x in self.items) + ']'

    def eval(self, m, env):
        return DSet(m.eval(x, env) for x in self.items)


@dataclass(frozen=True)
class Field(Expr):
    ty: Ty
    rec: Expr
    name: str

    def render(self, typed=False):
        return f'{atom(self.rec)}.{self.name}'

    def eval(self, m, env):
        return m.eval(self.rec, env).fields[self.name]


@dataclass(frozen=True)
class Index(Expr):
    ty: Ty
    coll: Expr
    at: Expr

    def render(self, typed=False):
        return f'{atom(self.coll)}[{render(self.at, True)}]'

    def eval(self, m, env):
        container, at = m.eval(self.coll, env), m.eval(self.at, env)
        if not 0 <= at < len(container):
            raise InvalidProgram('index out of range')
        return container[at]


@dataclass(frozen=True)
class Length(Expr):
    ty: Ty
    x: Expr

    def render(self, typed=False):
        return f'{atom(self.x)}.length'

    def eval(self, m, env):
        value = m.eval(self.x, env)
        return len(value.items if isinstance(value, DSet) else value)


@dataclass(frozen=True)
class Call(Expr):
    """A helper function or a closure variable (`closure` set) applied to arguments."""
    ty: Ty
    callee: str
    args: tuple
    closure: bool = False

    def render(self, typed=False):
        return f'{self.callee}(' + ' '.join(render(a, 'arg') for a in self.args) + ')'

    def eval(self, m, env):
        target = env.get(self.callee, m) if self.closure else m.functions[self.callee]
        return m.call(target, [m.eval(a, env) for a in self.args])


@dataclass(frozen=True)
class Method(Expr):
    ty: Ty
    recv: Expr
    name: str
    args: tuple = ()
    parens: bool = True

    def render(self, typed=False):
        args = '(' + ' '.join(render(a, 'arg') for a in self.args) + ')' if self.args or self.parens else ''
        return f'{atom(self.recv)}.{self.name}{args}'

    def eval(self, m, env):
        recv = m.eval(self.recv, env)
        args = [m.eval(a, env) for a in self.args]
        name = self.name
        if isinstance(recv, list):
            if name == 'push':
                recv.append(copy.deepcopy(args[0]))
                return None
            if name == 'pop':
                if not recv:
                    raise InvalidProgram('pop from an empty array')
                return recv.pop()
        if isinstance(recv, dict):
            if name == 'get':
                return copy.deepcopy(recv.get(args[0]))
            if name == 'keys':
                return copy.deepcopy(list(recv))
            if name == 'values':
                return copy.deepcopy(list(recv.values()))
            if name == 'remove':
                return recv.pop(args[0], m) is not m
        if isinstance(recv, DSet):
            if name == 'push':
                recv.items.setdefault(args[0])
                return None
            if name == 'remove':
                return recv.items.pop(args[0], m) is not m
        raise InvalidProgram(f'method {name}')


@dataclass(frozen=True)
class Ref(Expr):
    """`@place` as a call argument."""
    ty: Ty
    place: Expr

    def render(self, typed=False):
        return '@' + render(self.place)

    def eval(self, m, env):
        return m.place(self.place, env)


@dataclass(frozen=True)
class Lambda(Expr):
    ty: Ty
    params: tuple  # ((name, Ty), ...)
    result: Ty
    body: tuple

    def render(self, typed=False):
        params = ' '.join(f'{n}:{t}' for n, t in self.params)
        return f'({params}):>{self.result}=>{{\n{block(self.body)}\n}}'

    def eval(self, m, env):
        inner = bound_names(self) | {n for n, _ in self.params}
        captures = {}
        for name in sorted(free_names(self) - inner):
            if env.has(name):
                captures[name] = copy.deepcopy(env.get(name, m))
        return Closure(self.params, self.body, Scope(captures, None))


@dataclass(frozen=True)
class Interp(Expr):
    ty: Ty
    parts: tuple  # str or Expr

    def render(self, typed=False):
        return '"' + ''.join(escape(p) if isinstance(p, str) else '{' + render(p) + '}' for p in self.parts) + '"'

    def eval(self, m, env):
        return ''.join(p if isinstance(p, str) else show(m.eval(p, env)) for p in self.parts)


@dataclass(frozen=True)
class Conv(Expr):
    ty: Ty
    x: Expr

    def render(self, typed=False):
        return f'{self.ty}({render(self.x)})'

    def eval(self, m, env):
        value = m.eval(self.x, env)
        if self.ty == S:
            return show(value)
        if self.ty == F:
            return float(value)
        return wrap(value, self.ty)


@dataclass(frozen=True)
class OrThrow(Expr):
    """`x or_throw`: an error result returns from the enclosing function; otherwise its value."""
    ty: Ty
    x: Expr

    def render(self, typed=False):
        return f'({render(self.x)} or_throw)'

    def eval(self, m, env):
        value = m.eval(self.x, env)
        if member(value, BAD):
            raise Returned(value)
        return value


@dataclass(frozen=True)
class Narrow(Expr):
    """An implicit conversion of an `int` into a fixed-width destination: checked, not wrapped."""
    ty: Ty
    x: Expr

    def render(self, typed=False):
        return render(self.x, typed)

    def eval(self, m, env):
        value = m.eval(self.x, env)
        if not (0 <= value < 2 ** 64 if self.ty == U else -2 ** 63 <= value < 2 ** 63):
            raise Panicked('integer overflow')
        return value


@dataclass(frozen=True)
class Range(Expr):
    """`[start..stop)`, or `[start,second..stop]` with a step."""
    ty: Ty
    start: Expr
    second: Expr | None
    stop: Expr
    closed: bool

    def render(self, typed=False):
        # An untyped first bound fixes the counter as int64; bare bounds would make it `int`.
        head = render(self.start) + ('' if self.second is None else ',' + render(self.second, True))
        return f'[{head}..{render(self.stop, True)}' + (']' if self.closed else ')')

    def eval(self, m, env):
        start = m.eval(self.start, env)
        second = None if self.second is None else m.eval(self.second, env)
        stop = m.eval(self.stop, env)
        step = 1 if second is None else second - start
        if step == 0:
            raise InvalidProgram('zero range step')
        end = stop + (1 if step > 0 else -1) if self.closed else stop
        if abs(end - start) // abs(step) > 64:
            raise InvalidProgram('long range')
        return list(range(start, end, step))


@dataclass(frozen=True)
class Comp(Expr):
    """`[loop x in source if guard value]`, `key->value` for dicts, `set[...]` for sets."""
    ty: Ty
    names: tuple
    source: Expr
    guard: Expr | None
    value: Expr
    key: Expr | None = None

    def render(self, typed=False):
        binding = self.names[0] if len(self.names) == 1 else '[' + ' '.join(self.names) + ']'
        guard = '' if self.guard is None else f' if {render(self.guard)}'
        value = render(self.value, typed) if self.key is None else f'{render(self.key, typed)}->{render(self.value, typed)}'
        prefix = 'set' if self.ty.kind == 'set' else ''
        return f'{prefix}[loop {binding} in {render(self.source)}{guard} {value}]'

    def eval(self, m, env):
        result = {} if self.ty.kind == 'dict' else DSet(()) if self.ty.kind == 'set' else []
        for item in iterate(m.eval(self.source, env), len(self.names)):
            m.tick()
            local = Scope(dict(zip(self.names, item)), env)
            if self.guard is not None and not m.eval(self.guard, local):
                continue
            if self.key is not None:
                key = m.eval(self.key, local)
                result[key] = copy.deepcopy(m.eval(self.value, local))
            elif isinstance(result, DSet):
                result.items.setdefault(m.eval(self.value, local))
            else:
                result.append(copy.deepcopy(m.eval(self.value, local)))
        return result


# Statements -------------------------------------------------------------------

@dataclass(frozen=True)
class Let(Stmt):
    name: str
    ty: Ty
    value: Expr
    const: bool = False
    annotate: bool = True

    def render(self, typed=False):
        word = 'const' if self.const else 'let'
        if not self.annotate:
            return f'{word} {self.name}={render(self.value)}'
        return f'{word} {self.name}:{self.ty}={render(self.value, True)}'


@dataclass(frozen=True)
class Assign(Stmt):
    target: Expr
    value: Expr
    op: str = ''

    def render(self, typed=False):
        return f'{render(self.target)} {self.op}= {render(self.value, True)}'


@dataclass(frozen=True)
class Do(Stmt):
    expr: Expr

    def render(self, typed=False):
        return render(self.expr) + (';' if self.expr.ty != VOID else '')


@dataclass(frozen=True)
class Print(Stmt):
    expr: Expr
    juxtapose: bool = False

    def render(self, typed=False):
        if self.juxtapose and isinstance(self.expr, Interp):
            return 'printl' + render(self.expr)
        return f'printl({render(self.expr)})'


@dataclass(frozen=True)
class If(Stmt):
    test: Expr
    then: tuple
    other: tuple = ()

    def render(self, typed=False):
        text = f'if {render(self.test)} {{\n{block(self.then)}\n}}'
        if len(self.other) == 1 and isinstance(self.other[0], If):
            return text + ' else ' + render(self.other[0])
        if self.other:
            text += f' else {{\n{block(self.other)}\n}}'
        return text


@dataclass(frozen=True)
class Loop(Stmt):
    """`loop x in source`, `loop [k v] in dict`, `loop @x in array`; `other` is the else arm."""
    names: tuple
    source: Expr
    body: tuple
    mutable: bool = False
    other: tuple = ()

    def render(self, typed=False):
        binding = ('@' if self.mutable else '') + (self.names[0] if len(self.names) == 1
                                                   else '[' + ' '.join(self.names) + ']')
        text = f'loop {binding} in {render(self.source)} {{\n{block(self.body)}\n}}'
        return text + (f' else {{\n{block(self.other)}\n}}' if self.other else '')


@dataclass(frozen=True)
class While(Stmt):
    test: Expr
    body: tuple

    def render(self, typed=False):
        return f'loop {render(self.test)} {{\n{block(self.body)}\n}}'


@dataclass(frozen=True)
class Jump(Stmt):
    word: str  # break or continue

    def render(self, typed=False):
        return self.word


@dataclass(frozen=True)
class Return(Stmt):
    value: Expr | None
    implicit: bool = False

    def render(self, typed=False):
        if self.value is None:
            return 'return'
        return render(self.value, True) if self.implicit else f'return {render(self.value, True)}'


@dataclass(frozen=True)
class Assert(Stmt):
    """`$runtime_assert expr =? value`; a first oracle run fills in `expected`."""
    tag: int
    expr: Expr
    expected: Lit | None = None

    def render(self, typed=False):
        return f'$runtime_assert {render(self.expr)} =? {render(self.expected, True)}'


@dataclass(frozen=True)
class FuncDef(Node):
    name: str
    params: tuple  # ((name, Ty, mutable), ...)
    result: Ty | None
    body: tuple
    expression: bool = False  # `=>expr` instead of a block

    def render(self, typed=False):
        params = ' '.join(f'{"@" if mut else ""}{n}:{t}' for n, t, mut in self.params)
        result = '' if self.result is None else f':>{self.result}'
        if self.expression:
            return f'{self.name}=({params}){result}=>{render(self.body[0].value, True)}'
        return f'{self.name}=({params}){result}=>{{\n{block(self.body)}\n}}'


@dataclass(frozen=True)
class Program(Node):
    functions: tuple
    body: tuple

    def render(self, typed=False):
        parts = ['Item:type=[id:int64 tags:array<int64> label:string]', 'Bad:type=type of error & [code:int64]']
        parts += [render(f) for f in self.functions]
        parts.append('main=():>void=>{\n' + block(self.body) + '\n}')
        return '\n'.join(parts) + '\n'

    def source(self) -> str:
        return self.render()

    def expected(self) -> str:
        return self.outcome()[0]

    def outcome(self) -> tuple[str, int]:
        """Expected stdout and exit status (101 after a checked failure)."""
        machine = Machine(self.functions)
        try:
            machine.run(self.body)
        except Panicked:
            return ''.join(machine.output), 101
        return ''.join(machine.output), 0


def block(body) -> str:
    text = '\n'.join(render(s) for s in body)
    return '\n'.join('    ' + line for line in text.splitlines()) if text else '    '


# Oracle values and machine ------------------------------------------------------

class InvalidProgram(ValueError):
    """The program left the subset (a bound, an index, a lost definition): discard it."""


class Rec:
    __slots__ = ('fields', 'name')

    def __init__(self, name, fields):
        self.name, self.fields = name, fields

    def __eq__(self, other):
        return isinstance(other, Rec) and equal(self.fields, other.fields)

    def __hash__(self):
        raise TypeError('records are not keys here')

    def __deepcopy__(self, memo):
        return Rec(self.name, copy.deepcopy(self.fields, memo))


class DSet:
    """An insertion-ordered set (a dict without values), never Python's unordered set."""
    __slots__ = ('items',)

    def __init__(self, values):
        self.items = dict.fromkeys(values)

    def __eq__(self, other):
        return isinstance(other, DSet) and self.items.keys() == other.items.keys()

    def __deepcopy__(self, memo):
        return DSet(self.items)


class Closure:
    def __init__(self, params, body, scope):
        self.params, self.body, self.scope = params, body, scope

    def __deepcopy__(self, memo):
        # Copying a closure copies its private captured state.
        return Closure(self.params, self.body, Scope(copy.deepcopy(self.scope.vars, memo), None))


class Place:
    def __init__(self, container, key):
        self.container, self.key = container, key

    def get(self):
        return self.container[self.key]

    def set(self, value):
        self.container[self.key] = copy.deepcopy(value)


class Scope:
    __slots__ = ('parent', 'vars')

    def __init__(self, values, parent):
        self.vars, self.parent = values, parent

    def find(self, name):
        scope = self
        while scope is not None:
            if name in scope.vars:
                return scope
            scope = scope.parent
        return None

    def has(self, name):
        return self.find(name) is not None

    def place(self, name):
        scope = self.find(name)
        if scope is None:
            raise InvalidProgram(f'undefined {name}')
        value = scope.vars[name]
        return value if isinstance(value, Place) else Place(scope.vars, name)

    def get(self, name, m=None):
        return self.place(name).get()


class Panicked(Exception):
    """A checked failure the program must report: exit 101 (or a compile-time overflow error)."""


class Returned(Exception):
    def __init__(self, value):
        self.value = value


class Jumped(Exception):
    def __init__(self, word):
        self.word = word


def wrap(value, ty):
    if ty == INT:
        if not -2 ** 63 <= value < 2 ** 63:
            raise Panicked('integer overflow')
        return value
    if ty == I:
        value = int(value) & (2 ** 64 - 1)
        return value - 2 ** 64 if value >= 2 ** 63 else value
    if ty == U:
        return int(value) & (2 ** 64 - 1)
    if ty == F:
        return float(value)
    return value


def equal(x, y):
    if isinstance(x, float) or isinstance(y, float):
        return x == y
    if type(x) is not type(y) and not (x is None or y is None):
        return False
    return x == y


def iterate(source, names):
    if isinstance(source, DSet):
        items = list(source.items)
    elif isinstance(source, dict):
        items = [(k, v) for k, v in source.items()]
    elif isinstance(source, str):
        items = list(source)
    else:
        items = source
    items = copy.deepcopy(items)  # the input is a snapshot
    if names == 1:
        return [(x,) for x in items]
    return [tuple(x) for x in items]


def format_float(x: float) -> str:
    """Dewy's float text: shortest round-trip digits, exponent form outside [1e-5, 1e16)."""
    if math.isnan(x):
        return 'nan'
    if x == 0:
        return '-0.0' if math.copysign(1, x) < 0 else '0.0'
    sign = '-' if x < 0 else ''
    x = abs(x)
    if x == math.inf:
        return sign + 'inf'
    t = Decimal(repr(x)).as_tuple()
    exponent = len(t.digits) - 1 + t.exponent
    digits = ''.join(map(str, t.digits)).rstrip('0') or '0'
    if exponent >= 16 or exponent < -5:
        mantissa = digits[0] + ('.' + digits[1:] if len(digits) > 1 else '')
        return f'{sign}{mantissa}e{"-" if exponent < 0 else "+"}{abs(exponent)}'
    if exponent < 0:
        return f'{sign}0.{"0" * (-exponent - 1)}{digits}'
    whole = digits[:exponent + 1].ljust(exponent + 1, '0')
    return f'{sign}{whole}.{digits[exponent + 1:] or "0"}'


def show(value, nested=False) -> str:
    if value is None:
        return 'none'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format_float(value)
    if isinstance(value, str):
        if not nested:
            return value
        table = {'"': '\\"', '\\': '\\\\', '\n': '\\n', '\t': '\\t', '\r': '\\r'}
        return '"' + ''.join(table.get(c, c) for c in value) + '"'
    if isinstance(value, list):
        return '[' + ', '.join(show(x, True) for x in value) + ']'
    if isinstance(value, Rec):
        names = list(value.fields) if value.name else sorted(value.fields)
        inner = ', '.join(f'{n}={show(value.fields[n], True)}' for n in names)
        return f'{value.name or "<record>"}({inner})'
    if isinstance(value, dict):
        return '{' + ', '.join(f'{show(k, True)}: {show(v, True)}' for k, v in value.items()) + '}'
    if isinstance(value, DSet):
        return 'set[' + ', '.join(show(x, True) for x in value.items) + ']'
    raise InvalidProgram(f'cannot print {type(value).__name__}')


class Machine:
    def __init__(self, functions=(), fuel=60000):
        self.functions = {f.name: f for f in functions}
        self.output = []
        self.fuel = fuel
        self.depth = 0
        self.observed = {}

    def tick(self):
        self.fuel -= 1
        if self.fuel < 0:
            raise InvalidProgram('fuel exhausted')

    def eval(self, e, env):
        self.tick()
        return e.eval(self, env)

    def place(self, e, env, store=False):
        if isinstance(e, Var):
            return env.place(e.name)
        if isinstance(e, Field):
            return Place(self.place(e.rec, env).get().fields, e.name)
        if isinstance(e, Index):
            container = self.place(e.coll, env).get()
            at = self.eval(e.at, env)
            if isinstance(container, list) and not 0 <= at < len(container):
                raise InvalidProgram('index out of range')
            if isinstance(container, dict) and at not in container and not store:
                raise InvalidProgram('missing key')
            return Place(container, at)
        raise InvalidProgram('not a place')

    def call(self, target, arguments):
        self.depth += 1
        if self.depth > 40:
            raise InvalidProgram('deep recursion')
        try:
            if isinstance(target, FuncDef):
                params, scope = target.params, Scope({}, None)
            elif isinstance(target, Closure):
                params = tuple((n, t, False) for n, t in target.params)
                scope = Scope({}, target.scope)
            else:
                raise InvalidProgram('not callable')
            if len(params) != len(arguments):
                raise InvalidProgram('arity')
            for (name, _, mutable), value in zip(params, arguments):
                if mutable != isinstance(value, Place):
                    raise InvalidProgram('reference argument')
                scope.vars[name] = value if mutable else copy.deepcopy(value)
            try:
                if isinstance(target, FuncDef) and target.expression:
                    return copy.deepcopy(self.eval(target.body[0].value, scope))
                self.execute(target.body, scope)
                return None
            except Returned as result:
                return copy.deepcopy(result.value)
        finally:
            self.depth -= 1

    def run(self, body):
        try:
            self.execute(body, Scope({}, None))
        except Jumped:
            raise InvalidProgram('stray break') from None
        except (ZeroDivisionError, OverflowError, RecursionError, KeyError, TypeError) as error:
            raise InvalidProgram(f'oracle error: {error!r}') from None

    def execute(self, body, env):
        for s in body:
            self.tick()
            self.statement(s, env)

    def statement(self, s, env):
        if isinstance(s, Let):
            if s.name in env.vars:
                raise InvalidProgram('redefinition')
            env.vars[s.name] = copy.deepcopy(self.eval(s.value, env))
        elif isinstance(s, Assign):
            place = self.place(s.target, env, store=not s.op)
            value = self.eval(s.value, env)
            if s.op:
                ty = s.target.ty
                value = Bin(ty, s.op, Lit(ty, place.get()), Lit(ty, value)).eval(self, env)
            place.set(value)
        elif isinstance(s, Do):
            self.eval(s.expr, env)
        elif isinstance(s, Print):
            self.output.append(show(self.eval(s.expr, env)) + '\n')
        elif isinstance(s, If):
            self.execute(s.then if self.eval(s.test, env) else s.other, Scope({}, env))
        elif isinstance(s, Loop):
            self.loop(s, env)
        elif isinstance(s, While):
            while self.eval(s.test, env):
                try:
                    self.execute(s.body, Scope({}, env))
                except Jumped as jump:
                    if jump.word == 'break':
                        break
        elif isinstance(s, Jump):
            raise Jumped(s.word)
        elif isinstance(s, Return):
            raise Returned(None if s.value is None else self.eval(s.value, env))
        elif isinstance(s, Assert):
            value = self.eval(s.expr, env)
            if s.expected is None:
                self.observed.setdefault(s.tag, value)
            elif not equal(value, s.expected.value):
                raise InvalidProgram('assertion fails')
        else:
            raise InvalidProgram(type(s).__name__)

    def loop(self, s, env):
        source = self.place(s.source, env).get() if s.mutable else self.eval(s.source, env)
        if s.mutable:
            items = [(Place(source, i),) for i in range(len(source))]
        else:
            items = iterate(source, len(s.names))
        entered = False
        for item in items:
            self.tick()
            entered = True
            try:
                self.execute(s.body, Scope(dict(zip(s.names, item)), env))
            except Jumped as jump:
                if jump.word == 'break':
                    break
        if not entered and s.other:
            self.execute(s.other, Scope({}, env))


# Tree utilities ---------------------------------------------------------------

def children(node):
    for f in fields(node):
        yield from _nodes(getattr(node, f.name))


def _nodes(value):
    if isinstance(value, Node):
        yield value
    elif isinstance(value, tuple):
        for item in value:
            yield from _nodes(item)


def walk(node):
    yield node
    for child in children(node):
        yield from walk(child)


def transform(node, fn):
    """Rebuild bottom-up, applying `fn` to every node."""
    def visit(value):
        if isinstance(value, Node):
            changed = {f.name: visit(getattr(value, f.name)) for f in fields(value)}
            return fn(replace(value, **changed))
        if isinstance(value, tuple):
            return tuple(visit(item) for item in value)
        return value
    return visit(node)


def bound_names(node) -> set[str]:
    names = set()
    for n in walk(node):
        if isinstance(n, Let):
            names.add(n.name)
        elif isinstance(n, (Loop, Comp)):
            names.update(n.names)
        elif isinstance(n, MatchOpt):
            names.add(n.bind)
        elif isinstance(n, MatchUnion):
            names.update(a[0] for a in n.arms)
        elif isinstance(n, Lambda):
            names.update(p[0] for p in n.params)
    return names


def free_names(node) -> set[str]:
    used = {n.name for n in walk(node) if isinstance(n, Var)}
    used |= {n.callee for n in walk(node) if isinstance(n, Call) and n.closure}
    return used - bound_names(node)


def root(place):
    while isinstance(place, (Field, Index)):
        place = place.rec if isinstance(place, Field) else place.coll
    return place.name if isinstance(place, Var) else None


def effects(node, functions):
    """(names read, names written, produces output) for a statement or expression."""
    reads, writes, output = set(), set(), False
    printing = printing_functions(functions)
    for n in walk(node):
        if isinstance(n, (Print, Assert, Narrow)) or isinstance(n, (Bin, Unary)) and n.ty == INT:
            output = True  # observable: prints, or may stop the program
        if isinstance(n, Var):
            reads.add(n.name)
        elif isinstance(n, Let):
            writes.add(n.name)
        elif isinstance(n, Assign):
            writes.add(root(n.target))
        elif isinstance(n, Ref):
            writes.add(root(n.place))
        elif isinstance(n, Method) and n.name in MUTATING:
            writes.add(root(n.recv))
        elif isinstance(n, Loop):
            writes.update(n.names)
            if n.mutable:
                writes.add(root(n.source))
        elif isinstance(n, Comp):
            writes.update(n.names)
        elif isinstance(n, Call):
            if n.closure:
                reads.add(n.callee)
                writes.add(n.callee)
            elif n.callee in printing:
                output = True
    writes.discard(None)
    return reads, writes, output


def printing_functions(functions) -> set[str]:
    table = {f.name: f for f in functions}
    result = set()
    changed = True
    while changed:
        changed = False
        for f in functions:
            if f.name in result:
                continue
            for n in walk(f):
                if isinstance(n, Print) or (isinstance(n, Call) and not n.closure and n.callee in result):
                    result.add(f.name)
                    changed = True
                    break
    return result & set(table)


def pure(expr) -> bool:
    """No writes and no closure-state changes: safe to evaluate elsewhere, once."""
    for n in walk(expr):
        if isinstance(n, (Ref, Lambda, Assign)) or (isinstance(n, Method) and n.name in MUTATING):
            return False
        if isinstance(n, Call) and n.closure:
            return False
    return True


def scope_errors(program) -> list[str]:
    """Names used before (or outside) their definitions; shrink candidates must have none."""
    errors = []
    functions = {f.name for f in program.functions}

    def expr(e, visible):
        if isinstance(e, Var) and e.name not in visible:
            errors.append(e.name)
        elif isinstance(e, Call) and (e.callee not in visible if e.closure else e.callee not in functions):
            errors.append(e.callee)
        if isinstance(e, Lambda):
            stmts(e.body, visible | {n for n, _ in e.params})
            return
        extra = set()
        if isinstance(e, Comp):
            expr(e.source, visible)
            extra = set(e.names)
            for part in (e.guard, e.key, e.value):
                if part is not None:
                    expr(part, visible | extra)
            return
        if isinstance(e, MatchOpt):
            expr(e.subject, visible)
            expr(e.some, visible | {e.bind})
            expr(e.absent, visible)
            return
        if isinstance(e, MatchUnion):
            expr(e.subject, visible)
            for name, _, body in e.arms:
                expr(body, visible | {name})
            return
        for child in children(e):
            expr(child, visible)

    def stmts(body, visible):
        visible = set(visible)
        for s in body:
            if isinstance(s, Let):
                expr(s.value, visible)
                visible.add(s.name)
            elif isinstance(s, Loop):
                expr(s.source, visible)
                stmts(s.body, visible | set(s.names))
                stmts(s.other, visible)
            elif isinstance(s, (If, While)):
                expr(s.test, visible)
                stmts(s.then if isinstance(s, If) else s.body, visible)
                if isinstance(s, If):
                    stmts(s.other, visible)
            else:
                for child in children(s):
                    expr(child, visible)

    for f in program.functions:
        stmts(f.body, {p[0] for p in f.params})
    stmts(program.body, set())
    return errors


# Generator --------------------------------------------------------------------

FEATURES = ('arithmetic', 'floats', 'strings', 'records', 'arrays', 'snapshots', 'places',
            'closures', 'loops', 'comprehensions', 'branches', 'optionals', 'collections',
            'recursion', 'asserts', 'checked', 'errors')


@dataclass
class V:
    name: str
    ty: Ty
    mutable: bool = True
    minlen: int = 0  # arrays: a guaranteed lower bound on the length


class Generator:
    def __init__(self, seed, features=None):
        self.r = random.Random(seed)
        self.features = tuple(features or FEATURES)
        self.serial = 0
        self.functions: list[FuncDef] = []
        self.helpers: dict[str, list] = {}
        self.scopes: list[dict[str, V]] = [{}]
        self.loops = 0       # enclosing loops (break/continue allowed)
        self.guarded = 0     # inside a branch, loop or function: lengths are uncertain
        self.in_function = None
        self.asserts = 0

    # Scope ---------------------------------------------------------------------

    def fresh(self, prefix):
        self.serial += 1
        return f'{prefix}{self.serial}'

    def visible(self) -> dict[str, V]:
        result = {}
        for scope in self.scopes:
            result.update(scope)
        return result

    def pick(self, test):
        found = [v for v in self.visible().values() if test(v)]
        return self.r.choice(found) if found else None

    def declare(self, name, ty, mutable=True, minlen=0):
        self.scopes[-1][name] = V(name, ty, mutable, minlen)
        return self.scopes[-1][name]

    def nested(self, make, loop=False):
        self.scopes.append({})
        self.guarded += 1
        self.loops += loop
        try:
            return tuple(flatten(make()))
        finally:
            self.scopes.pop()
            self.guarded -= 1
            self.loops -= loop

    def chance(self, p):
        return self.r.random() < p

    # Literals ------------------------------------------------------------------

    def int_literal(self, ty=I):
        r = self.r
        if ty == U:
            return Lit(U, r.choice((0, 1, 2, 3, 7, 10, 255, 2 ** 32, 2 ** 63, 2 ** 64 - 1))
                       if self.chance(.2) else r.randint(0, 40))
        if self.chance(.1):
            return Lit(I, r.choice((-2 ** 63, 2 ** 63 - 1, 2 ** 31, -2 ** 31 - 1, 2 ** 62, 1 << 40, -1000003)))
        return Lit(I, r.randint(-20, 20))

    def float_literal(self):
        r = self.r
        if self.chance(.3):
            return Lit(F, r.choice((0.1, 0.2, 1.5, 2.25, 1e-3, 1e10, 3.0, 0.0, -0.5, 12345.678)))
        return Lit(F, r.randint(-40, 40) / r.choice((1, 2, 4, 8)))

    def literal(self, ty, depth=3):
        if ty in INTS:
            return self.int_literal(ty)
        if ty == F:
            return self.float_literal()
        if ty == B:
            return Lit(B, self.chance(.5))
        if ty == S:
            return Lit(S, self.r.choice(WORDS))
        return self.expr(ty, depth)

    # Expressions ---------------------------------------------------------------

    def expr(self, ty, depth=0):
        if ty.kind == 'array':
            return self.expr_array(ty, depth)
        if ty.kind == 'rec':
            return self.expr_record(ty, depth)
        method = getattr(self, f'expr_{ty.kind}', None) or getattr(self, f'expr_{ty}'.replace('|', '_'))
        return method(ty, depth)

    def leaf(self, ty, depth=3):
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and self.chance(.7):
            return Var(ty, v.name)
        return self.literal(ty, depth)

    def nonempty_array(self):
        return self.pick(lambda v: v.ty == AI and v.minlen > 0)

    def index_into(self, array: Expr, minlen: int, depth: int):
        if minlen and self.chance(.4):
            return Index(I, array, Lit(I, self.r.randrange(minlen)))
        at = self.expr(I, depth + 1)
        return Index(I, array, Bin(I, '%', at, Length(I, array)))

    def expr_int64(self, ty, depth):
        r = self.r
        if depth >= 3 or self.chance(.25):
            return self.leaf(I)
        choice = r.choice(('binary', 'binary', 'binary', 'unary', 'cond', 'match', 'length', 'field',
                           'index', 'call', 'closure', 'default', 'convert', 'optmatch', 'union'))
        d = depth + 1
        if choice == 'binary':
            op = r.choice(('+', '-', '*', '//', '%', 'xor', 'and', 'or', '<<', '>>', '^'))
            left = self.expr(I, d)
            if op in ('//', '%'):
                return Bin(I, op, left, Lit(I, r.choice((-7, -3, -1, 2, 3, 5, 8, 16, 1000))))
            if op in ('<<', '>>'):
                return Bin(I, op, left, Lit(I, r.randrange(64)))
            if op == '^':
                return Bin(I, op, left, Lit(I, r.randrange(5)))
            return Bin(I, op, left, self.expr(I, d))
        if choice == 'unary':
            return Unary(I, '-', self.expr(I, d))
        if choice == 'cond':
            return self.cond(I, d)
        if choice == 'match':
            keys = r.sample(range(-3, 6), r.randint(1, 3))
            return MatchLit(I, self.expr(I, d), tuple((Lit(I, k), self.expr(I, d)) for k in keys), self.expr(I, d))
        if choice == 'length':
            v = self.pick(lambda v: v.ty.kind in ('array', 'dict', 'set') or v.ty == S)
            if v is not None:
                return Length(I, Var(v.ty, v.name))
        if choice == 'field':
            v = self.pick(lambda v: v.ty in RECORDS)
            if v is not None:
                ty = v.ty
                rec = Var(ty, v.name)
                if ty == PAIR:
                    return Field(I, rec, 'right')
                if self.chance(.5):
                    return Field(I, rec, 'id' if ty == ITEM else 'value')
                xs = Field(AI, rec, 'tags' if ty == ITEM else 'xs')
                return self.index_into(xs, 1, d)
        if choice == 'index':
            v = self.nonempty_array()
            if v is not None:
                return self.index_into(Var(AI, v.name), v.minlen, d)
            v = self.pick(lambda v: v.ty == AAI and v.minlen > 0)
            if v is not None:
                outer = Index(AI, Var(AAI, v.name), Lit(I, self.r.randrange(v.minlen)))
                return self.index_into(outer, 1, d)
        if choice == 'call':
            helper = self.helper('pure')
            if helper is not None:
                return Call(I, helper.name, tuple(self.expr_array(t, d, nonempty=True) if t == AI else self.expr(t, d)
                                                  for _, t, _ in helper.params))
        if choice == 'closure' and 'closures' in self.features:
            v = self.pick(lambda v: v.ty == FN)
            if v is not None:
                return Call(I, v.name, (self.expr(I, d),), closure=True)
        if choice == 'default' and 'optionals' in self.features:
            v = self.pick(lambda v: v.ty == OI)
            if v is not None:
                return Bin(I, '??', Var(OI, v.name), self.expr(I, d))
            v = self.pick(lambda v: v.ty == DII)
            if v is not None:
                return Bin(I, '??', Method(OI, Var(DII, v.name), 'get', (self.expr(I, d),)), self.expr(I, d))
        if choice == 'convert':
            return Conv(I, self.expr(U, d))
        if choice == 'optmatch' and 'optionals' in self.features:
            v = self.pick(lambda v: v.ty == OI)
            if v is not None:
                bind = self.fresh('m')
                subject = Var(OI, v.name)
                self.scopes.append({bind: V(bind, I, False), **self.narrow(subject, I)})
                some = self.expr(I, d)
                self.scopes[-1] = self.narrow(subject, HIDDEN)
                absent = self.expr(I, d)
                self.scopes.pop()
                return MatchOpt(I, subject, bind, some, absent)
        if choice == 'union' and 'optionals' in self.features:
            v = self.pick(lambda v: v.ty == UIS)
            if v is not None:
                return self.union_match(Var(UIS, v.name), I, d)
        return self.leaf(I)

    def narrow(self, subject, ty):
        """A match arm or `if` test narrows a variable subject (HIDDEN: not usable there)."""
        return {subject.name: V(subject.name, ty, False)} if isinstance(subject, Var) else {}

    def union_match(self, subject, ty, depth):
        arms = []
        for member_ty in (I, S) if self.chance(.5) else (S, I):
            bind = self.fresh('m')
            self.scopes.append({bind: V(bind, member_ty, False), **self.narrow(subject, member_ty)})
            arms.append((bind, member_ty, self.expr(ty, depth)))
            self.scopes.pop()
        return MatchUnion(ty, subject, tuple(arms))

    def expr_uint64(self, ty, depth):
        r = self.r
        if depth >= 3 or self.chance(.3):
            return self.leaf(U)
        d = depth + 1
        choice = r.choice(('binary', 'binary', 'binary', 'convert', 'cond'))
        if choice == 'binary':
            op = r.choice(('+', '-', '*', '//', '%', 'xor', 'and', 'or', '<<', '>>'))
            left = self.expr(U, d)
            if op in ('//', '%'):
                return Bin(U, op, left, Lit(U, r.choice((1, 2, 3, 7, 10, 2 ** 32))))
            if op in ('<<', '>>'):
                return Bin(U, op, left, Lit(I, r.randrange(64)))
            return Bin(U, op, left, self.expr(U, d))
        if choice == 'convert':
            return Conv(U, self.expr(I, d))
        return self.cond(U, d)

    def expr_float64(self, ty, depth):
        r = self.r
        if depth >= 3 or self.chance(.3):
            return self.leaf(F)
        d = depth + 1
        choice = r.choice(('binary', 'binary', 'divide', 'convert', 'cond', 'field', 'index'))
        if choice == 'binary':
            return Bin(F, r.choice(('+', '-', '*')), self.expr(F, d), self.expr(F, d))
        if choice == 'divide':
            return Bin(F, '/', self.expr(F, d), Lit(F, r.choice((2.0, 4.0, 0.5, 3.0, 10.0, -8.0))))
        if choice == 'convert':
            return Conv(F, self.leaf(I))
        if choice == 'field':
            v = self.pick(lambda v: v.ty == PAIR)
            if v is not None:
                return Field(F, Var(PAIR, v.name), 'left')
        if choice == 'index':
            v = self.pick(lambda v: v.ty == AF and v.minlen > 0)
            if v is not None:
                return Index(F, Var(AF, v.name), Lit(I, r.randrange(v.minlen)))
        return self.cond(F, d)

    def expr_bool(self, ty, depth):
        r = self.r
        if depth >= 3 or self.chance(.15):
            v = self.pick(lambda v: v.ty == B)
            if v is not None and self.chance(.7):
                return Var(B, v.name)
            if self.chance(.8):  # a comparison of leaves beats a constant condition
                return Bin(B, r.choice(('<?', '>?', '=?', '>=?')), self.leaf(I), self.int_literal())
            return Lit(B, self.chance(.5))
        d = depth + 1
        choice = r.choice(('compare', 'compare', 'logic', 'not', 'equal', 'member'))
        if choice == 'compare':
            operand = r.choice((I, I, U, F))
            return Bin(B, r.choice(('=?', 'not=?', '<?', '>?', '<=?', '>=?')), self.expr(operand, d), self.expr(operand, d))
        if choice == 'logic':
            return Bin(B, r.choice(('and', 'or')), self.expr(B, d), self.expr(B, d))
        if choice == 'not':
            return Unary(B, 'not', self.expr(B, d))
        if choice == 'equal':
            v = self.pick(lambda v: v.ty in (S, AI, AS, DII, SI, ITEM, CELL))
            if v is not None:
                return Bin(B, r.choice(('=?', 'not=?')), Var(v.ty, v.name), self.expr(v.ty, d + 1))
        if choice == 'member':
            v = self.pick(lambda v: v.ty in (AI, SI, DII, S))
            if v is not None:
                needle = self.expr(S if v.ty == S else I, d)
                return Bin(B, 'in?', needle, Var(v.ty, v.name))
        return self.leaf(B)

    def test(self, depth):
        """A branch condition, sometimes an `is?` test; returns it and the names it narrows.

        Narrowed names are hidden inside both branches: the generator does not model the
        refined types there, and `is?` on an already-settled type is rejected.
        """
        v = self.pick(lambda v: v.ty in (OI, OS, UIS))
        if v is not None and self.chance(.25):
            test = 'none' if v.ty != UIS else self.r.choice(('int64', 'string'))
            return Is(B, Var(v.ty, v.name), test, self.chance(.5)), {v.name: V(v.name, HIDDEN, False)}
        return self.expr(B, depth), {}

    def branch(self, hidden, make):
        self.scopes.append(dict(hidden))
        try:
            return make()
        finally:
            self.scopes.pop()

    def cond(self, ty, depth):
        test, hidden = self.test(depth)
        return Cond(ty, test, self.branch(hidden, lambda: self.expr(ty, depth)),
                    self.branch(hidden, lambda: self.expr(ty, depth)))

    def expr_string(self, ty, depth):
        r = self.r
        if depth >= 3 or self.chance(.25):
            return self.leaf(S)
        d = depth + 1
        choice = r.choice(('interp', 'interp', 'concat', 'convert', 'cond', 'match', 'field', 'default', 'union'))
        if choice == 'interp':
            parts = []
            for _ in range(r.randint(1, 3)):
                parts.append(r.choice(('', 'v=', ' ', 'λ:', '[', 'é ')))
                parts.append(self.expr(r.choice((I, I, U, F, B, S, AI)), d + 1))
            return Interp(S, tuple(p for p in parts if p != ''))
        if choice == 'concat':
            return Bin(S, '+', self.expr(S, d), self.expr(S, d))
        if choice == 'convert':
            return Conv(S, self.expr(r.choice((I, U, F)), d))
        if choice == 'cond':
            return self.cond(S, d)
        if choice == 'match':
            keys = r.sample(range(4), r.randint(1, 2))
            return MatchLit(S, self.expr(I, d), tuple((Lit(I, k), self.expr(S, d)) for k in keys), self.expr(S, d))
        if choice == 'field':
            v = self.pick(lambda v: v.ty == ITEM)
            if v is not None:
                return Field(S, Var(ITEM, v.name), 'label')
        if choice == 'default' and 'optionals' in self.features:
            v = self.pick(lambda v: v.ty == OS)
            if v is not None:
                return Bin(S, '??', Var(OS, v.name), self.expr(S, d))
        if choice == 'union' and 'optionals' in self.features:
            v = self.pick(lambda v: v.ty == UIS)
            if v is not None:
                return self.union_match(Var(UIS, v.name), S, d)
        return self.leaf(S)

    def expr_array(self, ty, depth, nonempty=False):
        r = self.r
        element = ty.args[0]
        v = self.pick(lambda v: v.ty == ty and (v.minlen > 0 or not nonempty))
        if v is not None and (depth >= 3 or self.chance(.3)):
            return Var(ty, v.name)
        d = depth + 1
        choice = r.choice(('literal', 'literal', 'comp', 'keys', 'field'))
        if choice == 'comp' and not nonempty and 'comprehensions' in self.features and element != AI:
            return self.comprehension(ty, d)
        if choice == 'keys' and not nonempty and ty == AI:
            v = self.pick(lambda v: v.ty == DII)
            if v is not None:
                return Method(AI, Var(DII, v.name), r.choice(('keys', 'values')), parens=self.chance(.5))
        if choice == 'field' and ty == AI:
            v = self.pick(lambda v: v.ty in (ITEM, CELL))
            if v is not None:
                return Field(AI, Var(v.ty, v.name), 'tags' if v.ty == ITEM else 'xs')
        count = r.randint(1, 4)
        if element == AI:
            return ArrayLit(ty, tuple(self.expr_array(AI, d, nonempty=True) for _ in range(count)))
        return ArrayLit(ty, tuple(self.expr(element, d) for _ in range(count)))

    def comprehension(self, ty, depth):
        """An array, dict or set built by `loop` over a range, array, set or dict."""
        kind = ty.kind
        source, names, types = self.iterable(depth)
        self.scopes.append({n: V(n, t, False) for n, t in zip(names, types)})
        guard = self.expr(B, depth + 1) if self.chance(.5) else None
        if kind == 'dict':
            key = self.expr(ty.args[0], depth + 1)
            value = self.expr(ty.args[1], depth + 1)
        else:
            key, value = None, self.expr(ty.args[0], depth + 1)
        self.scopes.pop()
        return Comp(ty, names, source, guard, value, key)

    def iterable(self, depth):
        """(source, binding names, binding types) for loops and comprehensions."""
        r = self.r
        choice = r.choice(('range', 'range', 'array', 'set', 'dict', 'string'))
        name = self.fresh('i')
        if choice == 'array':
            v = self.pick(lambda v: v.ty in (AI, AS, AF))
            if v is not None:
                return Var(v.ty, v.name), (name,), (v.ty.args[0],)
        if choice == 'set':
            v = self.pick(lambda v: v.ty in (SI, SS))
            if v is not None:
                return Var(v.ty, v.name), (name,), (v.ty.args[0],)
        if choice == 'dict':
            v = self.pick(lambda v: v.ty in (DII, DSA))
            if v is not None:
                return Var(v.ty, v.name), (name, self.fresh('j')), v.ty.args
        if choice == 'string':
            v = self.pick(lambda v: v.ty == S)
            if v is not None:
                return Var(S, v.name), (name,), (S,)
        return self.range(), (name,), (I,)

    def range(self):
        r = self.r
        start = r.randint(-3, 4)
        step = r.choice((1, 1, 1, 2, 3, -1, -2))
        stop = start + step * r.randint(0, 6)
        start_expr = Lit(I, start)
        if self.chance(.3):
            v = self.pick(lambda v: v.ty == I and v.name.startswith('k'))
            if v is not None:  # loop counters are small
                start_expr = Var(I, v.name)
                stop = start + 3
        second = None if step == 1 and self.chance(.6) else Lit(I, start + step)
        if second is None:
            step = 1
            stop = max(stop, start)
        if isinstance(start_expr, Var):
            return Range(RANGE, start_expr, None, Bin(I, '+', start_expr, Lit(I, 3)), self.chance(.5))
        return Range(RANGE, start_expr, second, Lit(I, stop), self.chance(.5))

    def expr_record(self, ty, depth):
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and (depth >= 3 or self.chance(.3)):
            return Var(ty, v.name)
        d = depth + 1
        items = [(n, self.expr_array(t, d, nonempty=True) if t == AI else self.expr(t, d)) for n, t in ty.args]
        if ty.name and self.chance(.5):
            return RecLit(ty, tuple(items), positional=True)
        self.r.shuffle(items)
        return RecLit(ty, tuple(items))

    def expr_dict(self, ty, depth):
        r = self.r
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and (depth >= 3 or self.chance(.3)):
            return Var(ty, v.name)
        d = depth + 1
        if 'comprehensions' in self.features and self.chance(.25):
            return self.comprehension(ty, d)
        key_ty, value_ty = ty.args
        items = []
        for _ in range(r.randint(1, 4)):
            key = Lit(I, r.randint(-3, 6)) if key_ty == I else Lit(S, r.choice(WORDS[:8]))
            value = self.expr_array(AI, d, nonempty=True) if value_ty == AI else self.expr(value_ty, d)
            items.append((key, value))
        return DictLit(ty, tuple(items))

    def expr_set(self, ty, depth):
        r = self.r
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and (depth >= 3 or self.chance(.3)):
            return Var(ty, v.name)
        d = depth + 1
        if v is not None and self.chance(.3):
            return Bin(ty, r.choice(('|', '&', '-')), Var(ty, v.name), self.expr_set(ty, d))
        if 'comprehensions' in self.features and self.chance(.25):
            return self.comprehension(ty, d)
        element = ty.args[0]
        items = tuple(Lit(I, r.randint(-3, 8)) if element == I else Lit(S, r.choice(WORDS[:8]))
                      for _ in range(r.randint(1, 4)))
        return SetLit(ty, items)

    def expr_opt(self, ty, depth):
        inner = ty.args[0]
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and self.chance(.3):
            return Var(ty, v.name)
        if self.chance(.3):
            return Lit(ty, None)
        if inner == I and self.chance(.3):
            d = self.pick(lambda v: v.ty == DII)
            if d is not None:
                return Method(OI, Var(DII, d.name), 'get', (self.expr(I, depth + 1),))
        return self.expr(inner, depth + 1)

    def expr_union(self, ty, depth):
        v = self.pick(lambda v: v.ty == ty)
        if v is not None and self.chance(.3):
            return Var(ty, v.name)
        return self.expr(self.r.choice(ty.args), depth + 1)

    # Helpers -------------------------------------------------------------------

    def helper(self, kind):
        """An existing helper of this kind, or a new one (bounded)."""
        existing = self.helpers.setdefault(kind, [])
        if existing and (len(existing) >= 3 or self.chance(.6)):
            return self.r.choice(existing)
        if self.in_function is not None:
            return self.r.choice(existing) if existing else None
        made = getattr(self, f'make_{kind}')()
        if made is not None:
            existing.append(made)
            self.functions.append(made)
        return made

    def function_body(self, params, result, statements):
        saved = (self.scopes, self.in_function, self.loops, self.guarded)
        self.scopes = [{n: V(n, t, True, 1 if t.kind == 'array' else 0) for n, t, _ in params}]
        self.in_function, self.loops, self.guarded = result, 0, 1
        try:
            return statements()
        finally:
            self.scopes, self.in_function, self.loops, self.guarded = saved

    def make_pure(self):
        r = self.r
        name = self.fresh('h')
        params = tuple((self.fresh('p'), r.choice((I, I, U, AI, S)), False) for _ in range(r.randint(1, 3)))

        def body():
            if self.chance(.25):
                return (Return(self.expr(I, 1)),), True
            stmts = flatten(self.simple_statement(1) for _ in range(r.randint(1, 3)))
            stmts.append(Return(self.expr(I, 1), implicit=self.chance(.4)))
            return tuple(stmts), False
        stmts, expression = self.function_body(params, I, body)
        return FuncDef(name, params, I, stmts, expression)

    def make_mutator(self):
        """A void helper changing an `@` parameter: an integer, an array or a record."""
        r = self.r
        name = self.fresh('h')
        target_ty = r.choice((I, I, AI, AI, CELL, ITEM))
        target, delta = self.fresh('t'), self.fresh('p')
        params = ((target, target_ty, True), (delta, I, False))

        def body():
            stmts = []
            t = Var(target_ty, target)
            for _ in range(r.randint(1, 3)):
                if target_ty == I:
                    stmts.append(Assign(t, self.expr(I, 2), r.choice(('', '+', '*', '-'))))
                elif target_ty == AI:
                    if self.chance(.5):
                        stmts.append(Do(Method(VOID, t, 'push', (self.expr(I, 2),))))
                    else:
                        stmts.append(Assign(self.index_into(t, 1, 2), self.expr(I, 2), r.choice(('', '+'))))
                else:
                    field_name = 'id' if target_ty == ITEM else 'value'
                    xs = Field(AI, t, 'tags' if target_ty == ITEM else 'xs')
                    stmts.append(r.choice((
                        Assign(Field(I, t, field_name), self.expr(I, 2), r.choice(('', '+'))),
                        Do(Method(VOID, xs, 'push', (self.expr(I, 2),))),
                        Assign(self.index_into(xs, 1, 2), self.expr(I, 2)))))
            if self.chance(.3):
                stmts.append(Print(Interp(S, ('in ', name, ': ', t))))
            return tuple(stmts)
        return FuncDef(name, params, VOID, self.function_body(params, VOID, body))

    def make_recursive(self):
        r = self.r
        name = self.fresh('rec')
        n, acc = self.fresh('n'), self.fresh('acc')
        params = ((n, I, False), (acc, I, False))
        nv, av = Var(I, n), Var(I, acc)
        step = r.choice((Bin(I, '+', av, nv), Bin(I, 'xor', Bin(I, '*', av, Lit(I, 3)), nv),
                         Bin(I, '-', Bin(I, '*', av, Lit(I, 2)), nv), Bin(I, '+', av, Bin(I, '*', nv, nv))))
        recurse = Call(I, name, (Bin(I, '-', nv, Lit(I, r.choice((1, 2)))), step))
        if self.chance(.5):
            body = (If(Bin(B, '<=?', nv, Lit(I, 0)), (Return(av),)), Return(recurse, implicit=self.chance(.5)))
        else:
            body = (Return(Cond(I, Bin(B, '<=?', nv, Lit(I, 0)), av, recurse)),)
        return FuncDef(name, params, I, body)

    def make_fallible(self):
        """`(x:int64):>int64|Bad`: an error for some inputs, else a value."""
        r = self.r
        name, x = self.fresh('chk'), self.fresh('p')
        params = ((x, I, False),)

        def body():
            failing = Bin(B, r.choice(('<?', '>?', '=?')), Bin(I, '%', Var(I, x), Lit(I, r.choice((3, 4, 7)))),
                          Lit(I, r.randint(0, 2)))
            error = RecLit(BAD, (('code', self.expr(I, 2)),), positional=self.chance(.5))
            return (If(failing, (Return(error),)), Return(self.expr(I, 1)))
        return FuncDef(name, params, RESULT, self.function_body(params, RESULT, body))

    def make_propagating(self):
        """Calls fallible helpers through `or_throw`, so their errors return from it."""
        r = self.r
        inner = self.helper('fallible')
        name, x, v = self.fresh('prop'), self.fresh('p'), self.fresh('v')
        params = ((x, I, False),)

        def body():
            first = Let(v, I, OrThrow(I, Call(RESULT, inner.name, (self.expr(I, 2),))))
            self.declare(v, I)
            again = Call(RESULT, self.r.choice(self.helpers['fallible']).name, (Var(I, v),))
            result = Bin(I, r.choice(('+', '*', '-')), OrThrow(I, again), self.expr(I, 2))
            return (first, Return(result, implicit=self.chance(.4)))
        return FuncDef(name, params, RESULT, self.function_body(params, RESULT, body))

    def make_factory(self):
        """A function returning a counter closure: `(start)=>{let c=start return (s)=>{c+=s c}}`."""
        name, start, count, step = (self.fresh(p) for p in ('mk', 'p', 'c', 's'))
        op = self.r.choice(('+', '*', 'xor', '-'))
        update = Bin(I, op, Var(I, count), Var(I, step))
        lam = Lambda(FN, ((step, I),), I, (Assign(Var(I, count), update), Return(Var(I, count), True)))
        body = (Let(count, I, Var(I, start)), Return(lam))
        return FuncDef(name, ((start, I, False),), None, body)

    # Statements ----------------------------------------------------------------

    def printable(self):
        v = self.pick(lambda v: v.ty not in (FN, HIDDEN))
        if v is not None and self.chance(.6):
            return Var(v.ty, v.name)
        e = self.expr(self.r.choice(VALUE_TYPES), 1)
        return e if not (isinstance(e, Lit) and e.value is None) else Lit(S, 'none')

    def print_value(self, expr=None):
        expr = shown(expr if expr is not None else self.printable())
        if expr.ty == S and isinstance(expr, Interp):
            return Print(expr, juxtapose=self.chance(.5))
        if self.chance(.2):
            return Print(Interp(S, ('= ', expr)), juxtapose=True)
        return Print(expr)

    def new_variable(self, ty=None, const=False):
        ty = ty or self.r.choice(VALUE_TYPES)
        name = self.fresh({'int64': 'n', 'uint64': 'u', 'float64': 'f', 'bool': 'b', 'string': 's', 'array': 'xs',
                           'dict': 'd', 'set': 'st', 'opt': 'o', 'union': 'un', 'rec': 'r'}[ty.kind])
        value = self.expr_array(ty, 1, nonempty=self.chance(.8)) if ty.kind == 'array' else self.expr(ty, 1)
        self.declare(name, ty, not const, minlen(value, self.visible()))
        return Let(name, ty, value, const=const)

    def mutation(self, v: V, depth):
        """One change to a mutable variable, keeping the generator's length bounds."""
        r = self.r
        t = Var(v.ty, v.name)
        if v.ty in (I, U, F):
            return Assign(t, self.expr(v.ty, depth), r.choice(('', '+', '-', '*')))
        if v.ty in (B, S, OI, OS, UIS):
            return Assign(t, self.expr(v.ty, depth))
        if v.ty.kind == 'array':
            element = v.ty.args[0]
            choices = ['push', 'assign'] + ['index'] * (v.minlen > 0) + ['pop'] * (v.minlen > 1 and not self.guarded)
            choice = r.choice(choices)
            if choice == 'push':
                value = self.expr_array(AI, depth, nonempty=True) if element == AI else self.expr(element, depth)
                if not self.guarded:
                    v.minlen += 1
                return Do(Method(VOID, t, 'push', (value,)))
            if choice == 'pop':
                v.minlen -= 1
                return Do(Method(element, t, 'pop', (), self.chance(.5)))
            if choice == 'index':
                at = Lit(I, r.randrange(v.minlen)) if self.chance(.5) else Bin(I, '%', self.expr(I, depth), Length(I, t))
                if element == AI:
                    inner = Index(AI, t, at)
                    if self.chance(.5):
                        return Do(Method(VOID, inner, 'push', (self.expr(I, depth),)))
                    return Assign(self.index_into(inner, 1, depth), self.expr(I, depth), r.choice(('', '+')))
                if element == ITEM:
                    item = Index(ITEM, t, at)
                    return r.choice((
                        Assign(item, self.expr(ITEM, depth)),
                        Assign(Field(I, item, 'id'), self.expr(I, depth), r.choice(('', '+'))),
                        Assign(Field(S, item, 'label'), self.expr(S, depth)),
                        Do(Method(VOID, Field(AI, item, 'tags'), 'push', (self.expr(I, depth),))),
                        Assign(self.index_into(Field(AI, item, 'tags'), 1, depth), self.expr(I, depth))))
                op = r.choice(('', '+', '*')) if element in (I, F) else ''
                return Assign(Index(element, t, at), self.expr(element, depth), op)
            value = self.expr_array(v.ty, depth, nonempty=self.chance(.7))
            if not self.guarded:
                v.minlen = minlen(value, self.visible())
            else:
                v.minlen = min(v.minlen, minlen(value, self.visible()))
            return Assign(t, value)
        if v.ty.kind == 'rec':
            name, field_ty = r.choice(v.ty.args)
            target = Field(field_ty, t, name)
            if field_ty == AI:
                if self.chance(.5):
                    return Do(Method(VOID, target, 'push', (self.expr(I, depth),)))
                return Assign(self.index_into(target, 1, depth), self.expr(I, depth), r.choice(('', '+')))
            if r.random() < .2:
                return Assign(t, self.expr(v.ty, depth))
            return Assign(target, self.expr(field_ty, depth), r.choice(('', '+')) if field_ty in (I, F) else '')
        if v.ty.kind == 'dict':
            key_ty, value_ty = v.ty.args
            key = Lit(I, r.randint(-3, 6)) if key_ty == I else Lit(S, r.choice(WORDS[:8]))
            if self.chance(.3):
                return Do(Method(B, t, 'remove', (key,)))
            value = self.expr_array(AI, depth, nonempty=True) if value_ty == AI else self.expr(value_ty, depth)
            return Assign(Index(value_ty, t, key), value)
        if v.ty.kind == 'set':
            element = v.ty.args[0]
            key = Lit(I, r.randint(-3, 8)) if element == I else Lit(S, r.choice(WORDS[:8]))
            return Do(Method(B, t, 'remove', (key,))) if self.chance(.35) else Do(Method(VOID, t, 'push', (key,)))
        if v.ty == FN:
            return Do(Call(I, v.name, (self.expr(I, depth),), closure=True))
        raise ValueError(v.ty)

    def simple_statement(self, depth):
        r = self.r
        choice = r.choice(('mutate', 'mutate', 'mutate', 'print', 'let', 'if', 'loop', 'jump', 'ref'))
        if choice == 'mutate':
            v = self.pick(lambda v: v.mutable)
            if v is not None:
                return self.mutation(v, depth)
        if choice == 'print' and self.in_function is None:
            return self.print_value()
        if choice == 'if' and depth < 3:
            test, hidden = self.test(depth)
            then = self.branch(hidden, lambda: self.nested(
                lambda: [self.simple_statement(depth + 1) for _ in range(r.randint(1, 2))]))
            other = self.branch(hidden, lambda: self.nested(
                lambda: [self.simple_statement(depth + 1) for _ in range(r.randint(0, 2))]))
            return If(test, then, other)
        if choice == 'loop' and depth < 2 and 'loops' in self.features:
            return self.loop_statement(depth + 1)
        if choice == 'jump' and self.loops:
            return If(self.expr(B, depth + 1), (Jump(r.choice(('break', 'continue'))),))
        if choice == 'ref' and 'places' in self.features and self.in_function is None:
            call = self.ref_call(depth)
            if call is not None:
                return call
        return self.new_variable(r.choice(SCALARS + (AI,)))

    def loop_statement(self, depth, accumulate=None):
        r = self.r
        if self.chance(.15):
            v = self.pick(lambda v: v.mutable and v.ty in (AI, AF) and v.ty.kind == 'array')
            if v is not None:
                name = self.fresh('e')
                element = v.ty.args[0]

                def body():
                    self.declare(name, element)
                    return [Assign(Var(element, name), self.expr(element, depth + 1), r.choice(('', '+', '*')))]
                # A mutable loop may not resize its source: keep pushes and pops out of it.
                saved = v.mutable
                v.mutable = False
                stmts = self.nested(body, loop=True)
                v.mutable = saved
                return Loop((name,), Var(v.ty, v.name), stmts, mutable=True)
        if self.chance(.15):
            counter = self.fresh('k')
            limit = r.randint(0, 5)

            def body():
                stmts = [self.simple_statement(depth + 1) for _ in range(r.randint(1, 2))]
                return [Assign(Var(I, counter), Lit(I, 1), '+'), *stmts]
            self.declare(counter, I, mutable=False)
            loop = While(Bin(B, '<?', Var(I, counter), Lit(I, limit)), self.nested(body, loop=True))
            return _Seq((Let(counter, I, Lit(I, 0)), loop))
        source, names, types = self.iterable(depth)

        def body():
            for n, t in zip(names, types):
                self.declare(n, t, mutable=False)
            stmts = [self.simple_statement(depth + 1) for _ in range(r.randint(0 if accumulate else 1, 3))]
            if accumulate is not None:
                stmts.insert(r.randint(0, len(stmts)), Assign(Var(I, accumulate), self.expr(I, depth + 1), '+'))
            return stmts
        stmts = self.nested(body, loop=True)
        other = self.nested(lambda: [self.print_value(Lit(S, 'empty'))]) if self.chance(.15) and self.in_function is None else ()
        return Loop(names, source, stmts, other=other)

    def ref_call(self, depth):
        helper = self.helper('mutator')
        if helper is None:
            return None
        (_, target_ty, _), _ = helper.params
        places = self.places(target_ty)
        if not places:
            return None
        return Do(Call(VOID, helper.name, (Ref(target_ty, self.r.choice(places)), self.expr(I, depth))))

    def places(self, ty):
        """Mutable places of type `ty` for an `@` argument: variables, fields and elements."""
        r, found = self.r, []
        for v in self.visible().values():
            if not v.mutable:
                continue
            t = Var(v.ty, v.name)
            k = Lit(I, r.randrange(v.minlen)) if v.minlen else None
            nested = []
            if v.ty in (ITEM, CELL):
                nested.append(t)
            elif v.ty == AITEM and k is not None:
                nested.append(Index(ITEM, t, k))
            for rec in nested:
                if ty == rec.ty:
                    found.append(rec)
                if ty == I:
                    found.append(Field(I, rec, 'id' if rec.ty == ITEM else 'value'))
                if ty == AI:
                    found.append(Field(AI, rec, 'tags' if rec.ty == ITEM else 'xs'))
            if v.ty == ty and (ty != AI or v.minlen):
                found.append(t)
            if v.ty == AI and ty == I and k is not None:
                found.append(Index(I, t, k))
            if v.ty == AAI and k is not None:
                found.append(Index(AI, t, k) if ty == AI else Index(I, Index(AI, t, k), Lit(I, 0)) if ty == I else None)
        return [p for p in found if p is not None]

    # Feature blocks: each returns statements for main's top level ---------------

    def block_arithmetic(self):
        ty = self.r.choice((I, I, U))
        let = self.new_variable(ty)
        v = self.visible()[let.name]
        return [let, self.mutation(v, 1), self.print_value(Var(ty, v.name)),
                self.print_value(self.expr(ty, 0))]

    def block_floats(self):
        let = self.new_variable(F)
        out = [let, self.print_value(Var(F, let.name)), self.print_value(self.expr(B, 1))]
        if self.chance(.5):
            out.insert(1, self.new_variable(AF))
        return out

    def block_strings(self):
        let = self.new_variable(S)
        s = Var(S, let.name)
        return [let, self.print_value(Length(I, s)), self.print_value(self.expr(S, 0)),
                Print(Interp(S, ('<', s, '>')), juxtapose=True)]

    def block_records(self):
        let = self.new_variable(self.r.choice(RECORDS))
        v = self.visible()[let.name]
        return [let, *(self.mutation(v, 1) for _ in range(self.r.randint(1, 3))), self.print_value(Var(v.ty, v.name))]

    def block_arrays(self):
        let = self.new_variable(self.r.choice((AI, AI, AS, AAI, AITEM)))
        v = self.visible()[let.name]
        out = [let]
        for _ in range(self.r.randint(1, 4)):
            out.append(self.mutation(v, 1))
        out.append(self.print_value(Var(v.ty, v.name)))
        out.append(self.print_value(Length(I, Var(v.ty, v.name))))
        return out

    def block_snapshots(self):
        """`let saved = value` (or const), change the original, print both."""
        v = self.pick(lambda v: v.mutable and (v.ty.kind in ('array', 'rec', 'dict', 'set') or v.ty in (S, I)))
        out = []
        if v is None:
            out.append(self.new_variable(self.r.choice((AI, CELL, DII, SI))))
            v = self.visible()[out[-1].name]
        const = self.chance(.4)
        saved = self.fresh('saved')
        out.append(Let(saved, v.ty, Var(v.ty, v.name), const=const))
        self.declare(saved, v.ty, not const, v.minlen)
        for _ in range(self.r.randint(1, 3)):
            out.append(self.mutation(v, 1))
        out += [self.print_value(Var(v.ty, v.name)), self.print_value(Var(v.ty, saved))]
        return out

    def block_places(self):
        out = []
        for _ in range(self.r.randint(1, 2)):
            call = self.ref_call(1)
            if call is None:
                out.append(self.new_variable(self.r.choice((I, AI, CELL, ITEM))))
                call = self.ref_call(1)
            if call is not None:
                v = self.visible()[root(call.expr.args[0].place)]
                out += [call, self.print_value(Var(v.ty, v.name))]
        return out

    def block_closures(self):
        r = self.r
        name, copy_name = self.fresh('fn'), self.fresh('fn')
        out = []
        if r.random() < .4:
            factory = self.helper('factory')
            out.append(Let(name, FN, Call(FN, factory.name, (self.expr(I, 1),)), annotate=False))
        else:
            state = self.pick(lambda v: v.mutable and v.ty in (I, AI))
            if state is None:
                out.append(self.new_variable(I))
                state = self.visible()[out[-1].name]
            step = self.fresh('s')
            self.scopes.append({step: V(step, I, False)})
            self.guarded += 1
            captured = Var(state.ty, state.name)
            if state.ty == I:
                body = [Assign(captured, self.expr(I, 2), r.choice(('+', '-', '*', '')))]
                result = captured
            else:
                body = [Do(Method(VOID, captured, 'push', (Var(I, step),)))]
                result = Bin(I, '+', Length(I, captured), Var(I, step))
            self.guarded -= 1
            self.scopes.pop()
            out.append(Let(name, FN, Lambda(FN, ((step, I),), I, (*body, Return(result, implicit=r.random() < .5))),
                           annotate=False))
        self.declare(name, FN)
        out.append(self.print_value(Call(I, name, (self.expr(I, 1),), closure=True)))
        out.append(Let(copy_name, FN, Var(FN, name), annotate=False))
        self.declare(copy_name, FN)
        for _ in range(r.randint(1, 3)):
            which = r.choice((name, copy_name))
            out.append(self.print_value(Call(I, which, (self.expr(I, 1),), closure=True)))
        return out

    def block_loops(self):
        acc = self.fresh('n')
        self.declare(acc, I)
        out = [Let(acc, I, Lit(I, 0)), self.loop_statement(0, acc)]
        if self.chance(.5):
            out.append(self.loop_statement(0, acc))
        return flatten(out) + [self.print_value(Var(I, acc))]

    def block_comprehensions(self):
        r = self.r
        out = []
        if r.random() < .5:
            # The collect pattern the loop→comprehension variant rewrites.
            acc = self.fresh('xs')
            ty = r.choice((AI, AI, AS))
            source, names, types = self.iterable(1)
            self.scopes.append({n: V(n, t, False) for n, t in zip(names, types)})
            guard = self.expr(B, 2) if self.chance(.5) else None
            value = self.expr(ty.args[0], 2)
            self.scopes.pop()
            push = Do(Method(VOID, Var(ty, acc), 'push', (value,)))
            body = (push,) if guard is None else (If(guard, (push,)),)
            out += [Let(acc, ty, ArrayLit(ty, ())), Loop(names, source, body)]
            self.declare(acc, ty)
            name = acc
        else:
            ty = r.choice((AI, AI, AS, DII, SI, SS))
            name = self.fresh('c')
            out.append(Let(name, ty, self.comprehension(ty, 1)))
            self.declare(name, ty)
        out.append(self.print_value(Var(ty, name)))
        return out

    def block_branches(self):
        r = self.r
        out = [self.print_value(self.expr(r.choice((I, S)), 0))]
        test, hidden = self.test(0)
        then = self.branch(hidden, lambda: self.nested(lambda: [self.simple_statement(1) for _ in range(r.randint(1, 3))]))
        if self.chance(.4):
            def inner():
                test2, hidden2 = self.test(1)
                return If(test2, self.branch(hidden2, lambda: self.nested(lambda: [self.simple_statement(1)])),
                          self.branch(hidden2, lambda: self.nested(lambda: [self.simple_statement(1)])))
            out.append(If(test, then, (self.branch(hidden, inner),)))
        else:
            out.append(If(test, then, self.branch(hidden, lambda: self.nested(
                lambda: [self.simple_statement(1) for _ in range(r.randint(0, 2))]))))
        return out

    def block_optionals(self):
        r = self.r
        ty = r.choice((OI, OI, OS, UIS))
        let = self.new_variable(ty)
        v = Var(ty, let.name)
        out = [let]
        if ty == UIS:
            out.append(self.print_value(self.union_match(v, S, 1)))
            test, narrowed = r.choice((('int64', I), ('string', S)))
            cond = Is(B, v, test)
        else:
            narrowed = ty.args[0]
            cond = Is(B, v, 'none', negate=True)
        self.scopes.append({let.name: V(let.name, narrowed, False)})
        self.guarded += 1
        then = [self.print_value(self.expr(narrowed, 1) if self.chance(.5) else Var(narrowed, let.name))]
        then.append(self.simple_statement(2))
        self.guarded -= 1
        self.scopes.pop()
        out.append(If(cond, tuple(then), (self.print_value(Lit(S, 'absent')),)))  # no use of v there
        if ty != UIS:
            out.append(self.print_value(Bin(narrowed, '??', v, self.expr(narrowed, 1))))
        return out

    def block_collections(self):
        r = self.r
        let = self.new_variable(r.choice((DII, DII, DSA, SI, SS)))
        v = self.visible()[let.name]
        out = [let]
        for _ in range(r.randint(1, 4)):
            out.append(self.mutation(v, 1))
        t = Var(v.ty, v.name)
        out.append(self.print_value(t))
        if v.ty == DII:
            out.append(self.print_value(Method(OI, t, 'get', (Lit(I, r.randint(-3, 6)),))))
            out.append(self.print_value(Method(AI, t, r.choice(('keys', 'values')))))
        if self.chance(.5):
            out.append(self.loop_statement(1))
        return flatten(out)

    def block_recursion(self):
        helper = self.helper('recursive')
        depth = Lit(I, self.r.randint(0, 9)) if self.chance(.6) else Bin(I, '%', self.expr(I, 1), Lit(I, 10))
        return [self.print_value(Call(I, helper.name, (depth, self.expr(I, 1))))]

    def expr_int(self, ty, depth):
        """Checked `int`, straight-line only: every expression runs exactly once, so a
        compile-time overflow diagnostic and a runtime panic predict the same programs."""
        r = self.r
        v = self.pick(lambda v: v.ty == INT)
        if depth >= 3 or self.chance(.3):
            if v is not None and self.chance(.7):
                return Var(INT, v.name)
            if self.chance(.85):
                return Lit(INT, r.randint(-30, 30))
            return Lit(INT, r.choice((3037000499, 3037000500, 2 ** 40, 2 ** 62, -(2 ** 62), 2 ** 63 - 1)))
        d = depth + 1
        choice = r.choice(('binary', 'binary', 'mixed', 'negate', 'divide', 'power'))
        if choice == 'mixed':
            # `int` beside int64 computes as `int`; keep the int64 side a variable (a bare
            # literal next to an int64 operand would itself become int64 and wrap).
            n = self.pick(lambda v: v.ty == I)
            if n is not None and v is not None:
                pair = (Var(I, n.name), Var(INT, v.name))
                return Bin(INT, r.choice(('+', '-', '*')), *(pair if self.chance(.5) else pair[::-1]))
        if choice == 'negate':
            return Unary(INT, '-', self.expr(INT, d))
        if choice == 'divide':
            return Bin(INT, r.choice(('//', '%')), self.expr(INT, d), Lit(INT, r.choice((-7, -1, 2, 3, 10))))
        if choice == 'power':
            return Bin(INT, '^', self.expr(INT, d), Lit(INT, r.randint(0, 4)))
        return Bin(INT, r.choice(('+', '-', '*')), self.expr(INT, d), self.expr(INT, d))

    def block_checked(self):
        r = self.r
        out = []
        for _ in range(r.randint(1, 3)):
            name = self.fresh('z')
            out.append(Let(name, INT, self.expr(INT, 0), annotate=False))
            self.declare(name, INT, mutable=False)
            out.append(self.print_value(Var(INT, name)))
        z = Var(INT, out[-2].name)
        choice = r.choice(('int64', 'int64', 'uint64', 'update', 'update'))
        if choice == 'int64':
            # Literals alone in an int64 context are int64 (and wrap): an `int` variable
            # keeps the arithmetic checked.
            name = self.fresh('n')
            out.append(Let(name, I, Narrow(I, Bin(INT, r.choice(('+', '-', '*')), z, self.expr(INT, 1)))))
            self.declare(name, I)
            out.append(self.print_value(Var(I, name)))
        elif choice == 'uint64':
            # A negative `int` stored as uint64 is a checked failure, not a wrap.
            name = self.fresh('u')
            out.append(Let(name, U, Narrow(U, z)))
            self.declare(name, U)
            out.append(self.print_value(Var(U, name)))
        else:
            n = self.pick(lambda v: v.ty == I and v.mutable)
            if n is not None:
                out.append(Assign(Var(I, n.name), Narrow(I, Bin(INT, '+', Var(I, n.name), z))))
                out.append(self.print_value(Var(I, n.name)))
        return out

    def block_errors(self):
        r = self.r
        helper = self.helper(r.choice(('fallible', 'propagating')))
        name = self.fresh('res')
        out = [Let(name, RESULT, Call(RESULT, helper.name, (self.expr(I, 1),)))]
        self.declare(name, RESULT, mutable=False)
        res = Var(RESULT, name)
        value, error = self.fresh('m'), self.fresh('m')
        self.scopes.append({value: V(value, I, False), name: V(name, HIDDEN, False)})
        on_value = self.expr(I, 2)
        self.scopes[-1] = {name: V(name, HIDDEN, False)}
        on_error = Bin(I, '+', Field(I, Var(BAD, error), 'code'), self.expr(I, 2))
        self.scopes.pop()
        arms = [(value, I, on_value), (error, BAD, on_error)]
        if self.chance(.5):
            arms.reverse()
        out.append(self.print_value(res))
        out.append(self.print_value(MatchUnion(I, res, tuple(arms))))
        out.append(self.print_value(Is(B, res, r.choice(('Bad', 'error', 'int64')), self.chance(.3))))
        return out

    def block_asserts(self):
        self.asserts += 1
        ty = self.r.choice((I, I, B, S, U))
        return [Assert(self.asserts, self.expr(ty, 1))]

    # Programs ------------------------------------------------------------------

    def program(self) -> Program:
        r = self.r
        body = []
        for ty in r.sample((I, U, F, S, AI, CELL, DII, OI), r.randint(2, 5)):
            body.append(self.new_variable(ty))
        for _ in range(r.randint(4, 9)):
            feature = r.choice(self.features)
            body += getattr(self, f'block_{feature}')()
        if self.chance(.5):
            body += flatten([self.simple_statement(1) for _ in range(r.randint(1, 4))])
        for v in list(self.scopes[0].values()):
            if v.ty != FN and self.chance(.6):
                body.append(Print(shown(Var(v.ty, v.name))))
        return Program(tuple(self.functions), tuple(flatten(body)))


@dataclass(frozen=True)
class _Seq(Stmt):
    """Statements that belong together while generating; flattened before use."""
    items: tuple

    def render(self, typed=False):
        return '\n'.join(render(s) for s in self.items)


def flatten(stmts):
    out = []
    for s in stmts:
        if isinstance(s, _Seq):
            out.extend(s.items)
        else:
            out.append(s)
    return out


def shown(expr):
    return expr


def minlen(expr, scope) -> int:
    if isinstance(expr, ArrayLit):
        return len(expr.items)
    if isinstance(expr, Var) and expr.name in scope:
        return scope[expr.name].minlen
    if isinstance(expr, Field):
        return 1  # record arrays are never emptied
    if isinstance(expr, Cond):
        return min(minlen(expr.then, scope), minlen(expr.other, scope))
    return 0


def fill_asserts(program: Program) -> Program:
    """Run once to learn each assertion's value, then write it into the program."""
    machine = Machine(program.functions)
    try:
        machine.run(program.body)
    except Panicked:
        pass  # assertions after the failure never run
    observed = machine.observed

    def fill(node):
        if isinstance(node, Assert) and node.expected is None:
            value = observed.get(node.tag)
            if value is None and node.tag not in observed:
                return _Seq(())  # never executed
            return replace(node, expected=Lit(node.expr.ty, value))
        return node
    filled = transform(program, fill)
    return replace(filled, body=tuple(flatten(filled.body)))


def generate(seed: int, features=None, attempts: int = 25) -> tuple[Program, int]:
    """A valid program for this seed and how many candidates were discarded."""
    for attempt in range(attempts):
        try:
            program = fill_asserts(Generator(f'{seed}:{attempt}', features).program())
            program.expected()
            if scope_errors(program):
                raise InvalidProgram('scope')
            return program, attempt
        except InvalidProgram:
            continue
    raise InvalidProgram(f'no valid program for seed {seed}')


# Metamorphic variants -----------------------------------------------------------

def rename(node, old, new):
    def fn(n):
        if isinstance(n, Var) and n.name == old:
            return replace(n, name=new)
        if isinstance(n, Call) and n.closure and n.callee == old:
            return replace(n, callee=new)
        return n
    return transform(node, fn)


def variant_copy(program: Program, r: random.Random) -> Program | None:
    """`let b = a` at some point, then every later use of `a` becomes `b`."""
    body = list(program.body)
    lets = [i for i, s in enumerate(body) if isinstance(s, Let)]
    if not lets:
        return None
    i = r.choice(lets)
    s = body[i]
    position = r.randint(i + 1, len(body))
    copy_name = s.name + 'copy'
    later = tuple(rename(t, s.name, copy_name) for t in body[position:])
    insert = Let(copy_name, s.ty, Var(s.ty, s.name), annotate=s.annotate and s.ty != FN)
    return replace(program, body=tuple(body[:position]) + (insert,) + later)


def variant_reorder(program: Program, r: random.Random) -> Program | None:
    """Swap adjacent independent statements of main (no shared names, at most one output)."""
    body = list(program.body)
    info = [effects(s, program.functions) for s in body]
    swaps = 0
    for _ in range(len(body) * 2):
        i = r.randrange(len(body) - 1) if len(body) > 1 else 0
        if len(body) < 2:
            break
        (r1, w1, o1), (r2, w2, o2) = info[i], info[i + 1]
        if (o1 and o2) or w1 & (r2 | w2) or w2 & r1:
            continue
        body[i], body[i + 1] = body[i + 1], body[i]
        info[i], info[i + 1] = info[i + 1], info[i]
        swaps += 1
    return replace(program, body=tuple(body)) if swaps else None


def variant_outline(program: Program, r: random.Random) -> Program | None:
    """Move a pure expression into a new helper whose parameters are its free variables."""
    candidates = []
    places = set()
    for n in walk(program):
        # Places stay places: assignment targets, mutated receivers, `@` and `loop @` sources.
        target = (n.target if isinstance(n, Assign) else n.recv if isinstance(n, Method) and n.name in MUTATING
                  else n.place if isinstance(n, Ref) else n.source if isinstance(n, Loop) and n.mutable else None)
        while isinstance(target, (Field, Index)):
            places.add(id(target))
            target = target.rec if isinstance(target, Field) else target.coll
    for s in program.body:
        for n in walk(s):
            if (isinstance(n, Expr) and not isinstance(n, (Lit, Var, Range, Ref, Lambda)) and n.ty in VALUE_TYPES
                    and id(n) not in places and pure(n)
                    and not any(isinstance(x, Is) or isinstance(x, (ArrayLit, DictLit, SetLit)) and not x.items
                                for x in walk(n))):
                candidates.append(n)
    r.shuffle(candidates)
    for target in candidates:
        types = {}
        for n in walk(target):
            if isinstance(n, Var) and n.name in free_names(target) and (
                    types.setdefault(n.name, n.ty) != n.ty or n.ty == FN):
                break
        else:
            name = 'outlined' + str(len(program.functions))
            params = tuple((n + 'arg', t, False) for n, t in sorted(types.items()))
            body = rename_all(target, {n: n + 'arg' for n in types})
            helper = FuncDef(name, params, target.ty, (Let('result', target.ty, body), Return(Var(target.ty, 'result'))))
            call = Call(target.ty, name, tuple(Var(t, n) for n, t in sorted(types.items())))
            outlined = replace_node(program, target, call)
            return replace(outlined, functions=outlined.functions + (helper,))
    return None


def rename_all(node, names):
    for old, new in names.items():
        node = rename(node, old, new)
    return node


def variant_comprehension(program: Program, r: random.Random) -> Program | None:
    """`let acc=[]` + `loop x in s {acc.push(e)}` (optionally under `if g`) → `[loop x in s if g e]`."""
    def rewrite(body):
        body = list(body)
        for i in range(len(body) - 1):
            let, loop = body[i], body[i + 1]
            if not (isinstance(let, Let) and isinstance(let.value, ArrayLit) and not let.value.items
                    and isinstance(loop, Loop) and not loop.mutable and not loop.other and len(loop.body) == 1):
                continue
            inner, guard = loop.body[0], None
            if isinstance(inner, If) and len(inner.then) == 1 and not inner.other:
                guard, inner = inner.test, inner.then[0]
            if not (isinstance(inner, Do) and isinstance(inner.expr, Method) and inner.expr.name == 'push'
                    and isinstance(inner.expr.recv, Var) and inner.expr.recv.name == let.name):
                continue
            value = inner.expr.args[0]
            parts = [loop.source, value] + ([guard] if guard is not None else [])
            if any(let.name in free_names(p) or not pure(p) for p in parts):
                continue
            body[i:i + 2] = [Let(let.name, let.ty, Comp(let.ty, loop.names, loop.source, guard, value))]
            return tuple(body), True
        return tuple(body), False
    new_body, changed = rewrite(program.body)
    return replace(program, body=new_body) if changed else None


VARIANTS = {'copy': variant_copy, 'reorder': variant_reorder, 'outline': variant_outline,
            'comprehension': variant_comprehension}


def variants(program: Program, seed) -> dict[str, Program]:
    """Each applicable transform once, plus all of them composed; outputs must not change."""
    result = {}
    composed = program
    for name, make in VARIANTS.items():
        made = make(program, random.Random(f'{seed}:{name}'))
        if made is not None:
            result[name] = made
        again = make(composed, random.Random(f'{seed}:all:{name}'))
        composed = again if again is not None else composed
    if composed is not program and len(result) > 1:
        result['all'] = composed
    return result


# Shrinking ----------------------------------------------------------------------

def reductions(program: Program):
    """Smaller candidate programs, largest cuts first. Callers check validity."""
    body = program.body
    # Drop chunks of main, then single statements.
    n = len(body)
    size = n // 2
    while size >= 1:
        for start in range(0, n, size):
            yield replace(program, body=body[:start] + body[start + size:])
        size //= 2
    # Drop unused helpers.
    for f in program.functions:
        if not any(isinstance(x, Call) and x.callee == f.name for x in walk(program)):
            yield replace(program, functions=tuple(g for g in program.functions if g is not f))
    # Statement-level edits anywhere: delete, inline a branch or loop body.
    statements = [s for s in walk(program) if isinstance(s, Stmt)]
    for target in statements:
        options = [()]
        if isinstance(target, If):
            options += [target.then, target.other]
        if isinstance(target, Loop):
            options += [target.other, target.body]  # (a body using the loop variable is rejected)
        if isinstance(target, While):
            options.append(target.body)
        for option in options:
            yield replace_statement(program, target, option)
    # Expression edits: a same-typed child or a literal.
    for target in [e for e in walk(program) if isinstance(e, Expr)]:
        for smaller in simpler(target):
            yield replace_node(program, target, smaller)


def simpler(e):
    if isinstance(e, Lit):
        if e.ty in INTS and e.value not in (0, 1):
            yield replace(e, value=0)
            yield replace(e, value=1)
        if e.ty == S and e.value:
            yield replace(e, value='')
        return
    for child in children(e):
        if isinstance(child, Expr) and child.ty == e.ty and not isinstance(child, (Ref, Range)):
            yield child
    if e.ty in INTS:
        yield Lit(e.ty, 0)
    elif e.ty == F:
        yield Lit(F, 0.0)
    elif e.ty == B:
        yield Lit(B, False)
    elif e.ty == S:
        yield Lit(S, '')
    elif e.ty.kind == 'opt':
        yield Lit(e.ty, None)


def replace_node(program, target, new):
    done = [False]

    def visit(value):
        if done[0]:
            return value
        if value is target:
            done[0] = True
            return new
        if isinstance(value, Node):
            changed = {f.name: visit(getattr(value, f.name)) for f in fields(value)}
            if all(changed[k] is getattr(value, k) for k in changed):
                return value
            return replace(value, **changed)
        if isinstance(value, tuple):
            items = tuple(visit(x) for x in value)
            return value if all(a is b for a, b in zip(items, value)) else items
        return value
    return visit(program)


def replace_statement(program, target, statements):
    done = [False]

    def visit(value):
        if done[0]:
            return value
        if isinstance(value, tuple) and any(x is target for x in value):
            done[0] = True
            out = []
            for x in value:
                out.extend(statements if x is target else (x,))
            return tuple(out)
        if isinstance(value, Node):
            changed = {f.name: visit(getattr(value, f.name)) for f in fields(value)}
            if all(changed[k] is getattr(value, k) for k in changed):
                return value
            return replace(value, **changed)
        if isinstance(value, tuple):
            items = tuple(visit(x) for x in value)
            return value if all(a is b for a, b in zip(items, value)) else items
        return value
    return visit(program)


def valid(program: Program) -> bool:
    if scope_errors(program):
        return False
    for f in program.functions:
        if f.result not in (VOID, None) and not (f.body and isinstance(f.body[-1], Return)):
            return False
    try:
        program.expected()
    except InvalidProgram:
        return False
    return not any(stray_jumps(f.body) for f in program.functions) and not stray_jumps(program.body)


def stray_jumps(body) -> bool:
    """A `break` or `continue` outside every loop (shrinking can unwrap its loop)."""
    for s in body:
        if isinstance(s, Jump):
            return True
        if isinstance(s, If) and (stray_jumps(s.then) or stray_jumps(s.other)):
            return True
        if isinstance(s, Loop) and stray_jumps(s.other):
            return True
    return False


def size(program: Program) -> int:
    return sum(1 for _ in walk(program))
