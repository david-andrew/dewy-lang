"""Targeted differential fuzzing: small Dewy programs aimed at the lowering's special paths.

    python3 -m tools.compiler.dewy_fuzz_targeted [--seed N] [--count N] [--minutes M]
        [--families ...] [--modes ...] [--compiler PATH] [--print]

The general fuzzer (dewy_fuzz.py) grows whole programs from int64/uint64/int, strings and
collections. This one writes short focused tests, each checked against an independent Python
oracle: dense and sparse `match` over every integer width, enumerations and bools with every
scalar result type (lookup tables, jump tables, compare chains), and match statements whose
arms continue or break a loop; fixed-width arithmetic near the boundaries, shifts by constant
and runtime counts, division by assorted constants, mixing with `int`, conversions, and loops
over arrays of each width; short-circuit and comparison chains with side effects; closures
made in loops with early exits; array edits; grapheme and byte string slicing; float text.
Tests of one batch compile together as one program per mode (native default, -g and release;
web default and release); a failing test is rebuilt alone to confirm it, then shrunk to its
failing checks. Failures go to build/dewy-fuzz-failures/.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import math
import random
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from tools import cases
from tools.compiler.dewy_fuzz_programs import format_float

MODES = ('native', 'native-g', 'native-release', 'web', 'web-release')
MARK = '@@dewy-fuzz@@'
FAILURES = Path(__file__).resolve().parents[2] / 'build' / 'dewy-fuzz-failures'
SCRATCH = Path.home() / 'dev' / 'tmp' / 'dewy-fuzz-work'
RUN_TIMEOUT = 20


class Discard(Exception):
    """The generated test would have no defined result (an overflow, a bad index): draw another."""


# Integers ----------------------------------------------------------------------------

WIDTHS = {f'{s}int{b}': (b, s == '') for s in ('', 'u') for b in (8, 16, 32, 64)}
FIXED = tuple(WIDTHS)


def low(t):
    bits, signed = WIDTHS[t]
    return -(1 << bits - 1) if signed else 0


def high(t):
    bits, signed = WIDTHS[t]
    return (1 << bits - 1) - 1 if signed else (1 << bits) - 1


def wrap(v, t):
    if t == 'int':
        return v
    bits, signed = WIDTHS[t]
    v &= (1 << bits) - 1
    return v - (1 << bits) if signed and v >> bits - 1 else v


def fits(v, t):
    return t == 'int' or low(t) <= v <= high(t)


def interesting(r, t, near=()):
    """An integer of type t, often at an edge."""
    if t == 'int':
        pool = [0, 1, -1, 2, 7, -9, 100, 2 ** 31, 2 ** 32, 2 ** 63 - 1, 2 ** 63, -(2 ** 63), -(2 ** 63) - 1,
                2 ** 64, 2 ** 64 - 1, 2 ** 70, -(2 ** 70), 3037000500]
    else:
        lo, hi = low(t), high(t)
        pool = [0, 1, 2, 3, lo, lo + 1, hi, hi - 1, hi // 2, hi // 2 + 1, 7, 100]
        if lo < 0:
            pool += [-1, -2, lo // 2, -100]
        pool = [v for v in pool if lo <= v <= hi]
    pool += list(near)
    if r.random() < .4:
        return r.choice(pool)
    if t == 'int':
        return r.randint(-50, 50)
    return r.randint(max(low(t), -60), min(high(t), 60)) if r.random() < .6 else r.randint(low(t), high(t))


def float_text(x: float) -> str:
    """A float64 literal: always with a point or exponent, never `inf`/`nan`."""
    text = repr(x)
    if 'e' in text:
        mantissa, exponent = text.split('e')
        if '.' not in mantissa:
            mantissa += '.0'
        return f'{mantissa}e{exponent}'
    return text


def quote(text: str) -> str:
    table = {'\\': '\\\\', '"': '\\"', '{': '\\{', '}': '\\}', '\n': '\\n', '\t': '\\t'}
    return '"' + ''.join(table.get(c, c) for c in text) + '"'


# Tests ---------------------------------------------------------------------------------

@dataclass
class Test:
    family: str
    seed: int
    decls: list[str]                 # module-level declarations, names prefixed
    setup: list[str]                 # statements before the checks
    checks: list[tuple[str, str]]    # (statements, the output they give)
    prefix: str = 't_'

    @property
    def name(self):
        return f'{self.family}-seed{self.seed}'

    @property
    def expected(self) -> str:
        return ''.join(out for _, out in self.checks)

    def function(self) -> str:
        lines = [f'{self.prefix}run = ():>void => {{']
        lines += ['    ' + line for s in self.setup for line in s.splitlines()]
        lines += ['    ' + line for s, _ in self.checks for line in s.splitlines()]
        return '\n'.join(self.decls + lines + ['}'])

    def source(self) -> str:
        return self.function() + f'\nmain = ():>void => {self.prefix}run()\n'


def make(family, seed, prefix='t_') -> Test:
    r = random.Random(f'{family}:{seed}')
    for _ in range(50):
        try:
            test = FAMILIES[family](r, prefix)
        except Discard:
            continue
        test.family, test.seed, test.prefix = family, seed, prefix
        return test
    raise RuntimeError(f'{family} seed {seed}: no valid test in 50 draws')


def shell(family, decls, setup, checks):
    return Test(family, 0, decls, setup, checks)


def printing(expr: str, value: str) -> tuple[str, str]:
    return f'printl({expr})', value + '\n'


# Family: match ------------------------------------------------------------------------------

SUBJECTS = FIXED + ('int', 'int', 'int64', 'int64', 'enum', 'bool')
RESULTS = FIXED + ('int', 'int', 'int', 'bool', 'float64', 'string', 'enum')
WORDS = ('a', 'ok', 'é', 'λx', '🙂', 'two words', '', 'Z9')
FLOATS = (0.0, -0.0, 1.5, -2.25, 0.1, 1e-7, 1e16, 12345.678, -3.0, 2.5e-300, 1.7976931348623157e308)
ENUM = ('red', 'green', 'blue', 'cyan', 'mauve', 'x')


def scalar_value(r, t, prefix):
    """(source text, oracle value, printed text) of a constant of result type t."""
    if t == 'bool':
        v = r.random() < .5
        return ('true' if v else 'false'), v, ('true' if v else 'false')
    if t == 'float64':
        v = r.choice(FLOATS)
        return float_text(v), v, format_float(v)
    if t == 'string':
        v = r.choice(WORDS)
        return quote(v), v, v
    if t == 'enum':
        v = r.choice(ENUM[:4])
        return f"'{v}'", v, v
    v = interesting(r, t)
    return str(v), v, str(v)


def gen_match(r, p):
    st, rt = r.choice(SUBJECTS), r.choice(RESULTS)
    decls = []
    if rt == 'enum':
        decls.append(f"{p}R:type = " + ' | '.join(f"'{w}'" for w in ENUM[:4]))
    if st == 'enum':
        members = sorted(r.sample(ENUM, r.randint(2, 6)))
        decls.append(f"{p}E:type = " + ' | '.join(f"'{w}'" for w in members))
    rname = {'enum': f'{p}R'}.get(rt, rt)
    sname = {'enum': f'{p}E'}.get(st, st)
    # Keys
    if st == 'bool':
        universe = [False, True]
        keys = r.sample(universe, r.randint(1, 2))
    elif st == 'enum':
        universe = members
        keys = r.sample(members, r.randint(1, len(members)))
    else:
        count = r.choice((1, 2, 3, 3, 4, 5, 6, 8, 10, 14))
        lo, hi = (low(st), high(st)) if st != 'int' else (low('int64'), high('int64'))
        style = r.choice(('dense', 'dense', 'low', 'high', 'sparse', 'gappy'))
        if style == 'sparse':
            keys = [k for k in {interesting(r, st) for _ in range(count)} if lo <= k <= hi]
        else:
            base = {'low': lo, 'high': hi - count + 1}.get(style) if st != 'int' else None
            if base is None:
                base = r.choice((0, 0, 1, -2, -count, 250, 65530, 2 ** 31 - 3, 2 ** 63 - 5, 2 ** 64 - 4))
            step = 1 if style != 'gappy' else r.choice((2, 3, 7))
            keys = [base + i * step for i in range(count)]
            keys = [k for k in keys if lo <= k <= hi]
            r.shuffle(keys)
        if not keys:
            raise Discard
    keys = list(dict.fromkeys(keys))
    # (`<a|b>` and refinement patterns on an unsigned subject are rejected today: not generated)
    unsigned = st in FIXED and not WIDTHS[st][1]
    # Arms: groups of keys (an unsigned subject takes no `<a|b>` group: tracked separately)
    groups = []
    rest = list(keys)
    while rest:
        size = 1 if r.random() < .6 or unsigned or st == 'bool' else r.randint(2, 3)
        group = rest[:size]
        if st != 'enum' and len(group) > 1 and max(group) - min(group) + 1 - len(group) > 24:
            group = group[:1]  # (a singleton union may miss at most 24 values in its span)
        groups.append(group)
        rest = rest[len(group):]

    def key_text(k):
        if st == 'bool':
            return 'true' if k else 'false'
        if st == 'enum':
            return f"'{k}'"
        return str(k)

    table = r.random() < .5  # every arm a constant: the lookup-table shape

    def value_body():
        """An arm body: a constant (lookup-table eligible), a call, a block, or the subject."""
        text, v, shown = scalar_value(r, rt, p)
        roll = 1 if table else r.random()
        if roll < .12:
            return f'{p}id({text})', v, shown
        if roll < .2:
            return f'{{ {text} }}', v, shown
        if roll < .27 and rt == st and st not in ('enum', 'bool'):
            return 'x', None, None  # the subject itself
        return text, v, shown

    arms = []   # (pattern text, test(x) -> bool, body text, value or None (subject), shown)
    for group in groups:
        body, v, shown = value_body()
        pattern = '<' + '|'.join(key_text(k) for k in group) + '>'
        arms.append((pattern, group.__contains__, body, v, shown))
    numeric = st not in ('bool', 'enum')
    if numeric and not unsigned and r.random() < .25:
        bound = interesting(r, st if st != 'int' else 'int64')
        if bound >= high(st if st != 'int' else 'int64'):
            raise Discard
        body, v, shown = value_body()
        at = r.randrange(len(arms) + 1)
        earlier = {k for g in groups[:at] for k in g}
        top = high(st if st != 'int' else 'int64')
        if top - bound <= len(earlier) and all(k in earlier for k in range(bound + 1, top + 1)):
            raise Discard  # (the guard itself would be unreachable)
        # (an arm after the guard whose keys all pass it is unreachable: dropped)
        arms = arms[:at] + [(f'g:{st}<(>? {bound})>', bound.__lt__, body, v, shown)] + [
            arm for arm, group in zip(arms[at:], groups[at:]) if min(group) <= bound]
    covered = st == 'bool' and len(keys) == 2 or st == 'enum' and len(keys) == len(members)
    wildcard = not covered or r.random() < .3
    if covered and wildcard:
        raise Discard  # a wildcard after covering every member is an unreachable arm
    if wildcard:
        body, v, shown = value_body()
        if r.random() < .2 and numeric:
            arms.append(('other', lambda x: True, body, v, shown))
        else:
            arms.append(('_', lambda x: True, body, v, shown))
    decls.append(f'{p}id = (v:{rname}):>{rname} => v')
    text = 'match x {' + ' '.join(f'{pat} => {body}' for pat, _, body, _, _ in arms) + '}'
    plain = all(b != 'x' and not b.startswith(p) for _, _, b, _, _ in arms)
    form = r.choice(('typed', 'typed', 'let', 'block', 'inline')) if rt == 'int' and plain else r.choice(
        ('typed', 'typed', 'block', 'inline'))
    if form in ('typed', 'inline'):
        decls.append(f'{p}f = (x:{sname}):>{rname} => {text}')
    elif form == 'let':
        decls.append(f'{p}f = (x:{sname}) => {{ let n = {text}; n }}')
    else:
        decls.append(f'{p}f = (x:{sname}):>{rname} => {{\n    let n:{rname} = {text}\n    n\n}}')

    def oracle(x):
        for _, test, _, v, shown in arms:
            if test(x):
                if v is None:
                    return str(x)
                return shown
        raise AssertionError('no arm')

    # Inputs: every key, its neighbours, the edges.
    if st == 'bool':
        inputs = universe
    elif st == 'enum':
        inputs = list(members)
    else:
        inputs = set(keys)
        for k in keys:
            inputs |= {k - 1, k + 1}
        inputs |= {interesting(r, st) for _ in range(3)}
        if st != 'int':
            inputs |= {low(st), high(st), 0}
        inputs = sorted(v for v in inputs if fits(v, st))
        if len(inputs) > 16:
            inputs = sorted(r.sample(inputs, 16))
    setup, checks = [], []
    literal = key_text
    # Calls with literal arguments (constant folding), then a loop over a runtime array.
    for x in r.sample(inputs, min(len(inputs), 4)):
        checks.append(printing(f'{p}f({literal(x)})', oracle(x)))
    setup.append(f'let xs:array<{sname}> = [' + ' '.join(literal(x) for x in inputs) + ']')
    checks.append(('loop v in xs { printl(' + f'{p}f(v)' + ') }', ''.join(oracle(x) + '\n' for x in inputs)))
    if form == 'inline':
        # The match in the loop body itself, its subject the loop variable.
        checks.append((f'loop x in xs {{\n    let n:{rname} = {text}\n    printl(n)\n}}',
                       ''.join(oracle(x) + '\n' for x in inputs)))
    return shell('match', decls, setup, checks)


def gen_match_flow(r, p):
    """A match statement in a loop whose arms continue, break, print or update: jump tables
    whose arms leave through enclosing blocks; also a union subject."""
    # (literal arms on an optional are not supported: `none` and `_` only)
    st = r.choice(('int64', 'int8', 'uint8', 'int32', 'int', 'union'))
    base = r.choice((0, -3, 5, 120))
    keys = list(dict.fromkeys(base + r.randrange(12) for _ in range(r.randint(1, 8))))
    if st == 'uint8':
        keys = [k for k in keys if k >= 0]
    if st == 'int8':
        keys = [k for k in keys if k <= 127]
    if not keys:
        raise Discard
    actions = []
    for k in keys:
        actions.append((k, r.choice(('print', 'print', 'add', 'continue', 'continue', 'break', 'nested'))))
    if sum(a == 'break' for _, a in actions) > 1:
        raise Discard
    default = r.choice(('print', 'add', 'continue'))
    n = r.randint(3, 14)
    inputs = [base + r.randrange(-2, 14) for _ in range(n)]
    if st == 'uint8':
        inputs = [abs(x) for x in inputs]
    if st == 'int8':
        inputs = [min(x, 127) for x in inputs]
    if st == 'opt':
        inputs = [None if r.random() < .25 else x for x in inputs]
    if st == 'union':
        inputs = [r.choice(('s', 'tt')) if r.random() < .25 else x for x in inputs]

    def arm_text(action, k):
        return {'print': f'printl"k{k}"', 'add': f'{{ acc += {k} }}', 'continue': 'continue', 'break': 'break',
                'nested': f'{{ if acc >? {k} {{ printl"big" continue }}; acc -= 1 }}'}[action]

    arms = [f'<{k}> => {arm_text(a, k)}' for k, a in actions]
    if st == 'opt':
        arms.insert(r.randrange(len(arms) + 1), '<none> => { printl"none" continue }')
        typ = 'int64?'
    elif st == 'union':
        arms.insert(r.randrange(len(arms) + 1), 's:string => { printl(s) continue }')
        typ = 'int64|string'
    else:
        typ = st
    arms.append(f'_ => {arm_text(default, "d")}' if default != 'add' else '_ => { acc += 100 }')
    lits = ' '.join('none' if x is None else f'"{x}"' if isinstance(x, str) else f'({x})' if x < 0 else str(x)
                    for x in inputs)
    setup = [f'let xs:array<{typ}> = [{lits}]', 'let acc:int64 = 0']
    body = 'loop v in xs {\n    match v {\n' + ''.join(f'        {a}\n' for a in arms) + \
        '    }\n    printl"after {acc}"\n}\nprintl"end {acc}"'
    out, acc = [], 0
    table = dict(actions)
    for v in inputs:
        if v is None:
            out.append('none')
            continue
        if isinstance(v, str):
            out.append(v)
            continue
        action = table.get(v)
        if action is None:
            if default == 'add':
                acc += 100
            elif default == 'print':
                out.append('kd')
            else:
                continue
        elif action == 'print':
            out.append(f'k{v}')
        elif action == 'add':
            acc += v
        elif action == 'continue':
            continue
        elif action == 'break':
            break
        else:
            if acc > v:
                out.append('big')
                continue
            acc -= 1
        out.append(f'after {acc}')
    out.append(f'end {acc}')
    return shell('matchflow', [], setup, [(body, ''.join(line + '\n' for line in out))])


# Family: fixed-width arithmetic ------------------------------------------------------------

DIVISORS = (1, 2, 3, 5, 6, 7, 9, 10, 11, 16, 25, 100, 255, 641, 1000, 65537, 1000000007, 2 ** 32, 2 ** 32 + 1,
            2 ** 62 + 1, 2 ** 63 - 1, 2 ** 63, 2 ** 64 - 1)
LITERALS = (0, 1, 2, 3, 5, 7, 8, 10, 15, 16, 31, 63, 64, 100, 127, 255, 256, 1000, 2 ** 31 - 1, 2 ** 32, 2 ** 62)


def gen_arith(r, p):
    """Expressions over one fixed width (or `int`), with `int` mixed in.

    Explicit wrap conversions keep the fixed-width subexpressions at their modeled
    widths; ordinary arithmetic inside each conversion is exact. Division, remainder
    and power retain their widening model. Mathematical-int operands remain exact.
    """
    t = r.choice(FIXED + ('int', 'int64', 'int64', 'uint64'))
    names = [f'a{i}' for i in range(r.randint(2, 4))]
    values = {n: interesting(r, t) for n in names}
    zval = interesting(r, 'int')
    bits = WIDTHS[t][0] if t != 'int' else 64
    if t != 'int':
        counts = [f'c{i}' for i in range(2)]
        for c in counts:
            values[c] = r.choice((0, 1, 3, bits - 1, bits, bits + 1, r.randrange(bits), -1, 1 << bits - 1)) \
                if WIDTHS[t][1] or r.random() < .5 else r.choice((0, 1, bits - 1, bits, high(t)))
            values[c] = wrap(values[c], t)
    setup = [f'let {n}:{t} = {v}' for n, v in values.items()]
    mixed = t != 'int' and r.random() < .4
    if mixed:
        setup.append(f'let z:int = {zval}')
    exact_type = t if t in ('int', 'int64', 'uint64') else 'int64'

    def join(x, y):
        return 'int' if 'int' in (x, y) else x if x == y else 'int64'

    def word(text, ty):
        return text if ty == 'int' else f"{ty}({ty}<overflow='wrap'>({text}))"

    def leaf():
        if mixed and r.random() < .25:
            return 'z', zval, 'int'
        n = r.choice(names)
        return n, values[n], t

    def expr(depth):
        """(text, value, type): type is t or 'int'."""
        if depth >= 3 or r.random() < .2:
            return leaf()
        op = r.choice(('+', '-', '*', '+', '-', '*', '//', '%', 'and', 'or', 'xor', '<<', '>>', 'not', 'neg', '^',
                       'big'))
        a = expr(depth + 1)
        ty = a[2]
        if op == 'big':
            return f'bigint({a[0]})', a[1], 'int'
        if op == 'not':
            return word(f'(not {a[0]})', ty), wrap(~a[1], ty), ty
        if op == 'neg' and (ty == 'int' or WIDTHS[ty][1]):
            return word(f'(-{a[0]})', ty), wrap(-a[1], ty), ty
        if op in ('<<', '>>'):
            k = r.randrange(bits + 3) if r.random() < .8 else r.choice((0, 1, bits - 1))
            count = str(k)
            if ty != 'int' and r.random() < .4:
                # A runtime count: a fixed-width count is unsigned, so a negative one is huge.
                c = r.choice(counts)
                count, k = c, values[c] % (1 << WIDTHS[t][0])
            x = a[1]
            if ty == 'int':
                v = x << k if op == '<<' else x >> k
            elif k >= WIDTHS[ty][0]:
                v = 0 if op == '<<' or x >= 0 else -1
            else:
                v = wrap(x << k, ty) if op == '<<' else x >> k
            left = a[0] if ty == 'int' else f"{ty}<overflow='wrap'>({a[0]})"
            return word(f'({left} {op} {count})', ty), v, ty
        if op in ('//', '%'):
            d = r.choice(DIVISORS)
            if ty != 'int' and WIDTHS.get(ty, (0, True))[1] and r.random() < .3:
                d = -d
            b = (str(d) if d > 0 else f'({d})', d, ty) if fits(d, ty) and r.random() < .7 else expr(depth + 1)
            if b[1] == 0:
                raise Discard
            ty = 'int' if 'int' in (ty, b[2]) else exact_type if ty == b[2] == t else join(ty, b[2])
            v = a[1] // b[1] if op == '//' else a[1] % b[1]
            if not fits(v, ty):
                raise Discard
            return f'{ty}({a[0]} {op} {b[0]})', v, ty
        if op == '^':
            k = r.randrange(4)
            ty = 'int' if ty == 'int' else exact_type if ty == t else ty
            v = a[1] ** k
            if not fits(v, ty):
                raise Discard
            return f'{ty}({a[0]} ^ {k})', v, ty
        op = op if op in ('+', '-', '*', 'and', 'or', 'xor') else '+'
        b = expr(depth + 1)
        k = r.choice(LITERALS) * (-1 if r.random() < .3 else 1)
        if r.random() < .35 and fits(k, a[2]):
            # A literal on the right takes its left neighbour's type. (On the left it would
            # take the type the context expects instead: `w + (2 * x)` with w:int64, x:int8
            # computes in int64 while `w + (x * 2)` wraps in int8. Not generated.)
            b = (str(k) if k >= 0 else f'({k})', k, a[2])
        elif r.random() < .5:
            a, b = b, a
        ty = join(a[2], b[2])
        x, y = a[1], b[1]
        v = {'+': x + y, '-': x - y, '*': x * y, 'and': x & y, 'or': x | y, 'xor': x ^ y}[op]
        return word(f'({a[0]} {op} {b[0]})', ty), wrap(v, ty), ty

    checks = []
    for _ in range(r.randint(2, 6)):
        roll = r.random()
        if roll < .45:
            text, v, ty = expr(0)
            if text in names or text == 'z':
                continue
            if fits(v, t) and r.random() < .5:
                checks.append((f'let r{len(checks)}:{t} = {text}\nprintl(r{len(checks)})', f'{v}\n'))
            else:
                checks.append(printing(text, str(v)))
        elif roll < .6:
            # (an `int` right operand is narrowed to the width first, a checked conversion:
            # only same-width operands, whose update wraps)
            text, v, ty = expr(0)
            if ty != t:
                continue
            target = r.choice(names)
            op = r.choice(('+', '-', '*'))
            old = values[target]
            new = wrap({'+': old + v, '-': old - v, '*': old * v}[op], t)
            values[target] = new
            update = word(f'{target} {op} {text}', t)
            checks.append((f'{target} = {update}\nprintl({target})', f'{new}\n'))
        elif roll < .8:
            ops = r.choice((('<?', '<=?'), ('>?', '>=?'), ('=?',), ('not=?',)))
            n = 2 if ops == ('not=?',) else r.randint(2, 3)
            parts = [expr(1) for _ in range(n)]
            if len({ty for _, _, ty in parts}) > 1:
                continue  # (a comparison between widths converts the right operand: a checked narrowing)
            chosen = [r.choice(ops) for _ in range(n - 1)]
            result = all({'<?': x < y, '<=?': x <= y, '>?': x > y, '>=?': x >= y, '=?': x == y,
                          'not=?': x != y}[o] for o, (_, x, _), (_, y, _) in zip(chosen, parts, parts[1:]))
            text = parts[0][0] + ''.join(f' {o} {e}' for o, (e, _, _) in zip(chosen, parts[1:]))
            checks.append(printing(f'({text})', 'true' if result else 'false'))
        elif t in ('int', 'int64') and roll < .9:
            a, b = expr(1), expr(1)
            if b[1] == 0 or {a[2], b[2]} != {t}:
                continue
            kind = r.choice(('trunc', 'euclid', 'floor'))
            x, y = a[1], b[1]
            q = abs(x) // abs(y) * (1 if (x >= 0) == (y >= 0) else -1)
            v = {'floor': x % y, 'trunc': x - y * q, 'euclid': x % abs(y)}[kind]
            checks.append(printing(f"mod({a[0]} {b[0]} kind='{kind}')", str(v)))
        else:
            text, v, ty = expr(0)
            checks.append(printing(f'"<{{{text}}}>"', f'<{v}>'))
    if not checks:
        raise Discard
    return shell('arith', [], setup, checks)


# Family: short-circuit and comparison chains with side effects -------------------------------

def gen_effects(r, p):
    decls = [f'{p}b = (tag:int64 v:bool):>bool => {{ printl"b{{tag}}" v }}',
             f'{p}n = (tag:int64 v:int64):>int64 => {{ printl"n{{tag}}" v }}']
    counter = [0]

    def tag():
        counter[0] += 1
        return counter[0]

    def boolean(depth):
        """(text, run(trace) -> value)."""
        roll = r.random()
        if depth >= 3 or roll < .25:
            k, v = tag(), r.random() < .5
            return f'{p}b({k} {"true" if v else "false"})', lambda tr, k=k, v=v: (tr.append(f'b{k}'), v)[1]
        if roll < .5:
            ops = r.choice((('<?', '<=?', '=?'), ('>?', '>=?', '=?')))
            n = r.randint(2, 4)
            items = [(tag(), r.randint(-2, 2)) for _ in range(n)]
            chosen = [r.choice(ops) for _ in range(n - 1)]
            text = f'{p}n({items[0][0]} ({items[0][1]}))' + ''.join(
                f' {o} {p}n({k} ({v}))' for o, (k, v) in zip(chosen, items[1:]))

            def run(tr, items=items, chosen=chosen):
                tr.append(f'n{items[0][0]}')
                prev = items[0][1]
                for o, (k, v) in zip(chosen, items[1:]):
                    tr.append(f'n{k}')
                    if not {'<?': prev < v, '<=?': prev <= v, '>?': prev > v, '>=?': prev >= v, '=?': prev == v}[o]:
                        return False
                    prev = v
                return True
            return f'({text})', run
        if roll < .62:
            a = boolean(depth + 1)
            return f'(not {a[0]})', lambda tr, a=a: not a[1](tr)
        if roll < .72:
            c, x, y = boolean(depth + 1), boolean(depth + 1), boolean(depth + 1)
            return f'(if {c[0]} {x[0]} else {y[0]})', lambda tr, c=c, x=x, y=y: x[1](tr) if c[1](tr) else y[1](tr)
        op = r.choice(('and', 'or'))
        a, b = boolean(depth + 1), boolean(depth + 1)
        if op == 'and':
            return f'({a[0]} and {b[0]})', lambda tr, a=a, b=b: a[1](tr) and b[1](tr)
        return f'({a[0]} or {b[0]})', lambda tr, a=a, b=b: a[1](tr) or b[1](tr)

    checks = []
    for i in range(r.randint(2, 5)):
        text, run = boolean(0)
        trace = []
        v = run(trace)
        out = ''.join(t + '\n' for t in trace)
        shown = 'true' if v else 'false'
        form = r.choice(('print', 'if', 'let', 'while'))
        if form == 'print':
            checks.append((f'printl({text})', out + shown + '\n'))
        elif form == 'if':
            checks.append((f'if {text} {{ printl"yes" }} else {{ printl"no" }}', out + ('yes' if v else 'no') + '\n'))
        elif form == 'let':
            checks.append((f'let c{i} = {text}\nprintl(c{i})', out + shown + '\n'))
        else:
            # Evaluated once per test; the body runs once and leaves.
            checks.append((f'loop {text} {{ printl"in"; break }}\nprintl"after"',
                           out + ('in\n' if v else '') + 'after\n'))
    return shell('effects', decls, [], checks)


# Family: loops with early exits and closures made in them -------------------------------------

def gen_loops(r, p):
    lo, hi = r.randint(-3, 3), r.randint(0, 9)
    inclusive = r.random() < .4
    a, b, c = r.randint(2, 5), r.randint(-4, 4), r.randint(1, 4)
    mode = r.choice(('break', 'continue', 'both', 'none'))
    brk, cont = r.randint(lo, max(lo, hi) + 1), r.randint(2, 4)
    decls, setup, checks = [], [], []
    rng = f'[{lo}..{hi}{"]" if inclusive else ")"}'
    values = list(range(lo, hi + 1 if inclusive else hi))
    setup.append('let fs:array<<(x:int):>int>> = []')
    setup.append('let total:int = 0')
    setup.append('let seen:array<int> = []')
    body = []
    if mode in ('break', 'both'):
        body.append(f'if i =? {brk} break')
    if mode in ('continue', 'both'):
        body.append(f'if i % {cont} =? 0 continue')
    body.append(f'let k = i * {a} + {b}')
    body.append('fs.push((x:int):>int => x * i + k)')
    body.append('total += k')
    body.append('seen.push(i)')
    setup.append(f'loop i in {rng} {{\n    ' + '\n    '.join(body) + '\n}')
    fs, total, seen = [], 0, []
    for i in values:
        if mode in ('break', 'both') and i == brk:
            break
        if mode in ('continue', 'both') and i % cont == 0:
            continue
        k = i * a + b
        fs.append((i, k))
        total += k
        seen.append(i)
    checks.append(printing('seen', '[' + ' '.join(map(str, seen)) + ']'))
    checks.append(printing('total', str(total)))
    checks.append(('loop f in fs { printl(f(' + str(c) + ')) }', ''.join(f'{c * i + k}\n' for i, k in fs)))
    # A shared counter advanced by a closure called in a while loop with an early exit
    limit, step = r.randint(1, 30), r.randint(1, 5)
    checks.append(((f'let count = 0\nlet bump = ($capture @count) => {{ count += {step}; count }}\n'
                   f'let calls = 0\nloop bump() <? {limit} {{ calls += 1; if calls >? 6 break }}\n'
                   'printl"{count} {calls}"'), ''))
    count = calls = 0
    while True:
        count += step
        if not count < limit:
            break
        calls += 1
        if calls > 6:
            break
    checks[-1] = (checks[-1][0], f'{count} {calls}\n')
    # Private state: copies carry their own counter
    start = r.randint(-5, 5)
    checks.append(((f'let made = () => {{ let n = {start}; return ($capture n) => {{ n += 1; n }} }}\n'
                   'let g1 = made()\ng1();\nlet g2 = @g1\nprintl"{g1()} {g2()} {g1()}"'),
                   f'{start + 2} {start + 2} {start + 3}\n'))
    return shell('loops', decls, setup, checks)


# Family: arrays --------------------------------------------------------------------------------

def gen_arrays(r, p):
    xs = [r.randint(-9, 9) for _ in range(r.randint(0, 6))]
    setup = ['let xs:array<int64> = [' + ' '.join(map(str, xs)) + ']']
    checks = []
    ys = None
    for _ in range(r.randint(3, 10)):
        op = r.choice(('push', 'insert', 'insert', 'pop', 'popi', 'set', 'add', 'truncate', 'slice', 'incl',
                       'clamp', 'copy', 'copy', 'end', 'length', 'extend'))
        n = len(xs)
        v = r.randint(-20, 20)
        if op == 'push':
            xs.append(v)
            checks.append((f'xs.push({v})\nprintl(xs)', show(xs)))
        elif op == 'insert':
            i = r.randint(0, n)
            xs.insert(i, v)
            checks.append((f'xs.insert({v} {i})\nprintl(xs)', show(xs)))
        elif op == 'pop' and n:
            checks.append(('printl(xs.pop())', f'{xs.pop()}\n'))
        elif op == 'popi' and n:
            i = r.randrange(n)
            checks.append((f'printl(xs.pop({i}))', f'{xs.pop(i)}\n'))
        elif op == 'set' and n:
            i = r.randrange(n)
            xs[i] = v
            checks.append((f'xs[{i}] = {v}\nprintl(xs)', show(xs)))
        elif op == 'add' and n:
            i = r.randrange(n)
            xs[i] += v
            checks.append((f'xs[{i}] += {v}\nprintl(xs[{i}])', f'{xs[i]}\n'))
        elif op == 'truncate':
            k = r.randint(0, n)
            del xs[k:]
            checks.append((f'xs.truncate({k})\nprintl(xs)', show(xs)))
        elif op == 'slice':
            i = r.randint(0, n)
            j = r.randint(i, n)
            checks.append((f'printl(xs[{i}..{j}))', show(xs[i:j])))
        elif op == 'incl' and n:
            i = r.randrange(n)
            j = r.randint(i, n - 1)
            checks.append((f'printl(xs[{i}..{j}])', show(xs[i:j + 1])))
        elif op == 'clamp':
            i, j = r.randint(-2, n + 2), r.randint(-2, n + 3)
            ci = min(max(i, 0), n)
            cj = max(min(max(j, 0), n), ci)
            checks.append((f'printl(xs[$clamp ({i})..({j})))', show(xs[ci:cj])))
        elif op == 'copy':
            ys = list(xs)
            name = f'c{len(checks)}'
            checks.append((f'let {name} = xs\n{name}.push({v})\nxs.push({-v})\nprintl"{{{name}}} {{xs}}"',
                           show(ys + [v])[:-1] + ' ' + show(xs + [-v])))
            xs.append(-v)
        elif op == 'end' and n:
            checks.append(('printl(xs[end])', f'{xs[-1]}\n'))
        elif op == 'length':
            checks.append(('printl(xs.length)', f'{n}\n'))
        elif op == 'extend':
            extra = [r.randint(-5, 5) for _ in range(r.randint(0, 3))]
            xs.extend(extra)
            checks.append(('xs.extend([' + ' '.join(map(str, extra)) + '])\nprintl(xs)', show(xs)))
    if not checks:
        raise Discard
    return shell('arrays', [], setup, checks)


def show(xs):
    return '[' + ' '.join(map(str, xs)) + ']\n'


# Family: strings ------------------------------------------------------------------------------

CHARS = ('a', 'b', 'Z', ' ', 'é', 'λ', '🙂', 'ß', '=', '0')


def gen_strings(r, p):
    s = ''.join(r.choice(CHARS) for _ in range(r.randint(0, 9)))
    setup = [f'let s = {quote(s)}']
    checks = []
    n = len(s)
    data = s.encode()
    starts = [i for i in range(len(data) + 1) if i == len(data) or data[i] & 0xC0 != 0x80]
    for _ in range(r.randint(3, 8)):
        op = r.choice(('index', 'slice', 'incl', 'bytes', 'length', 'find', 'count', 'starts', 'upper', 'loop',
                       'interp', 'compare'))
        if op == 'index' and n:
            i = r.randrange(n)
            checks.append(printing(f's[{i}]', s[i]))
        elif op == 'slice':
            i = r.randint(0, n)
            j = r.randint(i, n)
            checks.append(printing(f's[{i}..{j})', s[i:j]))
        elif op == 'incl' and n:
            i = r.randrange(n)
            j = r.randint(i, n - 1)
            checks.append(printing(f's[{i}..{j}]', s[i:j + 1]))
        elif op == 'bytes':
            i = r.choice(starts)
            j = r.choice([x for x in starts if x >= i])
            checks.append(printing(f's.byte_slice({i} {j})', data[i:j].decode()))
        elif op == 'length':
            checks.append(printing('s.length', str(n)))
        elif op == 'find':
            part = r.choice(CHARS) if r.random() < .5 or not n else s[r.randrange(n):][:2]
            checks.append(printing(f's.find({quote(part)}) ?? -1', str(s.find(part))))
        elif op == 'count':
            part = r.choice(CHARS + ('ab', 'a a'))
            checks.append(printing(f's.count({quote(part)})', str(s.count(part))))
        elif op == 'starts':
            part = s[:r.randint(0, n)] if r.random() < .6 else r.choice(CHARS)
            checks.append(printing(f's.startswith({quote(part)})', 'true' if s.startswith(part) else 'false'))
        elif op == 'upper':
            # (simple one-to-one mappings: ß stays ß)
            checks.append(printing('s.upper()', ''.join(c.upper() if len(c.upper()) == 1 else c for c in s)))
        elif op == 'loop':
            checks.append(('loop c in s { if c =? " " continue; if c =? "=" break; print"<{c}>" }\nprintl""',
                           ''.join(f'<{c}>' for c in s.split('=')[0] if c != ' ') + '\n'))
        elif op == 'interp':
            i = r.randint(0, n)
            checks.append(printing(f'"[{{s[0..{i})}}|{{s.length}}]"', f'[{s[:i]}|{n}]'))
        elif op == 'compare':
            t = ''.join(r.choice(CHARS) for _ in range(r.randint(0, 3)))
            if r.random() < .3:
                t = s
            ops = {'=?': s == t, '<?': s < t, '>=?': s >= t}
            o = r.choice(list(ops))
            checks.append(printing(f'(s {o} {quote(t)})', 'true' if ops[o] else 'false'))
    if not checks:
        raise Discard
    return shell('strings', [], setup, checks)


# Family: fixed-width kernels -------------------------------------------------------------------

def gen_kernels(r, p):
    """Loops over arrays of a fixed width: accumulators, in-place element updates, counts.

    The optimizer's loop paths (induction variables, hoisting, unrolling, element access
    without bounds checks) meet narrow-width wrapping here.
    """
    t = r.choice(FIXED + ('int64', 'uint8', 'int8'))
    n = r.choice((0, 1, 2, 3, 5, 8, 9, 16, 17))
    xs = [interesting(r, t) for _ in range(n)]
    setup = [f'let xs:array<{t}> = [' + ' '.join(map(str, xs)) + ']']
    checks = []
    for i in range(r.randint(2, 5)):
        kind = r.choice(('sum', 'mix', 'max', 'xor', 'exact', 'update', 'index', 'count', 'while', 'pairs'))
        acc0 = interesting(r, t)
        name = f'acc{i}'
        if kind == 'sum':
            v = acc0
            for x in xs:
                v = wrap(v + x, t)
            checks.append((f'let {name}:{t} = {acc0}\nloop x in xs {{ {name} += x }}\nprintl({name})', f'{v}\n'))
        elif kind == 'mix':
            k = r.choice((3, 5, 31, 127))
            v = acc0
            for x in xs:
                v = wrap(wrap(v * k, t) + x, t)
            checks.append(((f'let {name}:{t} = {acc0}\nlet k{i}:{t} = {k}\n'
                           f'loop x in xs {{ {name} = {name} * k{i} + x }}\nprintl({name})'), f'{v}\n'))
        elif kind == 'max':
            v = acc0
            for x in xs:
                v = max(v, x)
            checks.append((f'let {name}:{t} = {acc0}\nloop x in xs {{ if x >? {name} {name} = x }}\nprintl({name})',
                           f'{v}\n'))
        elif kind == 'xor':
            v = acc0
            for x in xs:
                v = wrap(v ^ x, t)
            checks.append((f'let {name}:{t} = {acc0}\nloop x in xs {{ {name} xor= x }}\nprintl({name})', f'{v}\n'))
        elif kind == 'exact':
            v = sum(xs) + acc0
            checks.append((f'let {name}:int = {acc0}\nloop x in xs {{ {name} += x }}\nprintl({name})', f'{v}\n'))
        elif kind == 'update':
            k = interesting(r, t)
            op = r.choice(('+', '-', '*', 'xor'))
            for j, x in enumerate(xs):
                xs[j] = wrap({'+': x + k, '-': x - k, '*': x * k, 'xor': x ^ k}[op], t)
            how = r.choice(('index', 'place'))
            if how == 'index':
                text = f'let k{i}:{t} = {k}\nloop j in [0..xs.length) {{ xs[j] {op}= k{i} }}\nprintl(xs)'
            else:
                text = f'let k{i}:{t} = {k}\nloop @x in xs {{ x {op}= k{i} }}\nprintl(xs)'
            checks.append((text, '[' + ' '.join(map(str, xs)) + ']\n'))
        elif kind == 'index' and n >= 2:
            # Each element against its neighbour, through indices.
            v = acc0
            for j in range(n - 1):
                v = wrap(v + wrap(xs[j + 1] - xs[j], t), t)
            checks.append(((f'let {name}:{t} = {acc0}\nloop j in [0..xs.length - 1) {{ {name} += xs[j + 1] - xs[j] }}\n'
                           f'printl({name})'), f'{v}\n'))
        elif kind == 'count':
            bound = interesting(r, t)
            v = sum(1 for x in xs if x < bound)
            checks.append(((f'let {name} = 0\nlet b{i}:{t} = {bound}\nloop x in xs {{ if x <? b{i} {name} += 1 }}\n'
                           f'printl({name})'), f'{v}\n'))
        elif kind == 'while':
            stop = interesting(r, t)
            v, j = acc0, 0
            while j < n:
                if xs[j] == stop:
                    break
                v = wrap(v - xs[j], t)
                j += 1
            checks.append(((f'let {name}:{t} = {acc0}\nlet j{i} = 0\nlet s{i}:{t} = {stop}\n'
                           f'loop j{i} <? xs.length {{\n    if xs[j{i}] =? s{i} break\n    {name} -= xs[j{i}]\n'
                           f'    j{i} += 1\n}}\nprintl"{{{name}}} {{j{i}}}"'), f'{v} {j}\n'))
        elif kind == 'pairs' and n:
            v = 0
            for a in xs:
                for b in xs:
                    if b == a:
                        break
                    v += 1 if a > b else 0
            checks.append(((f'let {name} = 0\nloop a in xs {{\n    loop b in xs {{\n        if b =? a break\n'
                           f'        if a >? b {name} += 1\n    }}\n}}\nprintl({name})'), f'{v}\n'))
    if not checks:
        raise Discard
    # These kernels deliberately exercise wrapping, now an explicit policy.
    word = f'{p}Word'
    render = lambda text: re.sub(rf'\b{t}\b', word, text)
    return shell('kernels', [f"{word}:type = {t}<overflow='wrap'>"],
                 [render(text) for text in setup], [(render(text), out) for text, out in checks])


# Family: conversions -----------------------------------------------------------------------------

def gen_convert(r, p):
    """Float to integer truncation, integer to float rounding, wrapping and saturating policies."""
    checks, setup = [], []
    for i in range(r.randint(2, 6)):
        kind = r.choice(('trunc', 'tofloat', 'wrap', 'saturate', 'widen'))
        if kind == 'trunc':
            t = r.choice(FIXED + ('int',))
            x = r.choice((0.5, -0.5, 1.9999, -1.9999, 127.9, -128.9, 255.99, 2147483647.5, 4294967295.9,
                          9.2233720368547e18, -9.2233720368547e18, 1.8446744073709e19, 1e20, 3.0, -0.0, 65535.5))
            v = int(x)
            if not fits(v, t):
                continue
            setup.append(f'let f{i}:float64 = {float_text(x)}')
            checks.append(printing(f'{t}(f{i})', str(v)))
        elif kind == 'tofloat':
            t = r.choice(FIXED + ('int',))
            v = interesting(r, t)
            if t == 'int' and abs(v) > 2 ** 1000:
                continue
            setup.append(f'let n{i}:{t} = {v}')
            checks.append(printing(f'float64(n{i})', format_float(float(v))))
        elif kind == 'wrap':
            s, t = r.choice(FIXED + ('int',)), r.choice(FIXED)
            v = interesting(r, s)
            setup.append(f'let n{i}:{s} = {v}')
            checks.append(printing(f"{t}<overflow='wrap'>(n{i})", str(wrap(v, t))))
        elif kind == 'saturate':
            s, t = r.choice(FIXED + ('int',)), r.choice(FIXED)
            v = interesting(r, s)
            setup.append(f'let n{i}:{s} = {v}')
            checks.append(printing(f"{t}<overflow='saturate'>(n{i})", str(min(max(v, low(t)), high(t)))))
        else:
            s, t = r.choice(FIXED), r.choice(FIXED + ('int',))
            v = interesting(r, s)
            if not fits(v, t):
                continue
            setup.append(f'let n{i}:{s} = {v}')
            checks.append(printing(f'{t}(n{i})', str(v)))
    if not checks:
        raise Discard
    return shell('convert', [], setup, checks)


# Family: float text ---------------------------------------------------------------------------

FLOAT_SEEDS = (0.0, -0.0, 0.1, 0.2, 0.3, 1.0, 3.0, 1e-5, 9.99999e-6, 1e16, 9999999999999998.0, 1e15, 123456.789,
               5e-324, 2.2250738585072014e-308, 1.7976931348623157e308, 1e21, 1e-7, 2.5, 100.0, 7.0, 1 / 3)


def gen_floats(r, p):
    names = [f'f{i}' for i in range(r.randint(2, 4))]
    values = {n: r.choice(FLOAT_SEEDS) * r.choice((1, 1, -1)) for n in names}
    setup = [f'let {n}:float64 = {float_text(v)}' for n, v in values.items()]
    checks = []

    def expr(depth):
        if depth >= 3 or r.random() < .3:
            n = r.choice(names)
            return n, values[n]
        op = r.choice(('+', '-', '*', '/'))
        a, b = expr(depth + 1), expr(depth + 1)
        x, y = a[1], b[1]
        try:
            v = {'+': lambda: x + y, '-': lambda: x - y, '*': lambda: x * y}[op]() if op != '/' else divide(x, y)
        except OverflowError:
            v = math.copysign(math.inf, 1.0)
        return f'({a[0]} {op} {b[0]})', v

    for i in range(r.randint(2, 6)):
        text, v = expr(0)
        if math.isnan(v):
            checks.append(printing(f'({text} =? {text})', 'false'))
            continue
        form = r.choice(('print', 'interp', 'string'))
        if form == 'print':
            checks.append(printing(text, format_float(v)))
        elif form == 'interp':
            checks.append(printing(f'"<{{{text}}}>"', f'<{format_float(v)}>'))
        else:
            checks.append(printing(f'string({text}).length', str(len(format_float(v)))))
    return shell('floats', [], setup, checks)


def divide(x, y):
    if y == 0:
        if x == 0 or math.isnan(x):
            return math.nan
        return math.copysign(math.inf, x) * math.copysign(1.0, y)
    return x / y


FAMILIES = {'match': gen_match, 'matchflow': gen_match_flow, 'arith': gen_arith, 'kernels': gen_kernels, 'convert': gen_convert,
            'effects': gen_effects, 'loops': gen_loops, 'arrays': gen_arrays, 'strings': gen_strings,
            'floats': gen_floats}
WEIGHTS = {'match': 4, 'matchflow': 2, 'arith': 3, 'kernels': 2, 'convert': 1, 'effects': 1, 'loops': 1, 'arrays': 1,
           'strings': 1, 'floats': 1}


def families_for(seed, chosen):
    """The family of a seed: weighted, deterministic."""
    pool = [f for f in chosen for _ in range(WEIGHTS[f])]
    return pool[seed % len(pool)]


# Running ---------------------------------------------------------------------------------------

class Runner(cases.Runner):
    def flags(self, mode):
        return super().flags(mode) + (['-g'] if mode.endswith('-g') else [])


@dataclass
class Failure:
    test: Test
    mode: str
    kind: str      # reject, crash, mismatch, batch-only
    detail: str
    actual: str = ''


def first_error(text: str) -> str:
    for line in text.splitlines():
        if ': error: ' in line:
            return line.split(': error: ', 1)[1].strip()
    return text.strip().splitlines()[-1] if text.strip() else 'build failed'


class Fuzzer:
    def __init__(self, compiler: Path, modes, scratch: Path):
        node = shutil.which('node')
        if node is None and any(m.startswith('web') for m in modes):
            raise RuntimeError('web modes need Node; pass --modes native native-g native-release')
        self.modes = tuple(modes)
        self.runner = Runner(compiler, scratch, cases.clean_environment(), node)

    def outcome(self, test: Test, mode: str):
        """('pass'|'reject'|'crash'|'mismatch', detail, actual) for one test alone."""
        work = self.runner.directory('single')
        source = work / 'program.dewy'
        source.write_text(test.source())
        output = work / 'program'
        built = self.runner.build(source, output, mode)
        if built.returncode:
            text = built.stdout + built.stderr
            return 'reject', first_error(text), text
        code, stdout, stderr = self.runner.execute(self.runner.command(output, mode), timeout=RUN_TIMEOUT)
        if code != 0:
            return 'crash', f'exit {code}', stdout + stderr
        if stdout != test.expected:
            return 'mismatch', 'stdout differs from the oracle', stdout
        return 'pass', '', stdout

    def confirm(self, test, mode, kind, detail):
        alone, alone_detail, actual = self.outcome(test, mode)
        if alone == 'pass':
            return [Failure(test, mode, 'batch-only', f'{kind} ({detail}) only inside a batch')]
        return [Failure(test, mode, alone, alone_detail, actual)]

    def run_batch(self, batch: list[Test], mode: str) -> list[Failure]:
        """Compile the tests as one program, run it once and judge each test."""
        failures = []
        batch = list(batch)
        while batch:
            work = self.runner.directory(mode)
            lines, owner = [], []
            for i, t in enumerate(batch):
                text = t.function().splitlines()
                lines += text
                owner += [i] * len(text)
            lines.append('main = ():>void => {')
            for i, t in enumerate(batch):
                lines += [f'    printl"{MARK}B{i}"', f'    {t.prefix}run()', f'    printl"{MARK}E{i}"']
            source = work / 'batch.dewy'
            source.write_text('\n'.join(lines) + '\n}\n')
            output = work / 'batch'
            built = self.runner.build(source, output, mode)
            if built.returncode == 0:
                break
            text = built.stdout + built.stderr
            located = re.search(r'batch\.dewy:(\d+):\d+: error', text)
            line = int(located[1]) - 1 if located else -1
            if not 0 <= line < len(owner):
                # Unattributable: judge each test alone (which also runs those that build).
                alone = [(t, self.outcome(t, mode)) for t in batch]
                failures += [Failure(t, mode, o[0], o[1], o[2]) for t, o in alone if o[0] != 'pass']
                if not any(o[0] == 'reject' for _, o in alone):
                    failures.append(Failure(batch[0], mode, 'batch-only', f'reject ({first_error(text)}) only in a batch'))
                return failures
            failures += self.confirm(batch.pop(owner[line]), mode, 'reject', first_error(text))
        if not batch:
            return failures
        code, stdout, _ = self.runner.execute(self.runner.command(output, mode), timeout=RUN_TIMEOUT * 3)
        results, started = parse(stdout)
        for i, test in enumerate(batch):
            if i in results:
                if results[i] != test.expected:
                    failures += self.confirm(test, mode, 'mismatch', 'stdout differs from the oracle')
            else:
                failures += self.confirm(test, mode, 'crash', f'exit {code} (test {started} was running)')
                rest = batch[i + 1:]
                return failures + (self.run_batch(rest, mode) if rest else [])
        return failures

    def shrink(self, failure: Failure) -> Test:
        """Drop checks (and setup lines) while the same kind of failure remains."""
        test = failure.test
        progress = True
        while progress:
            progress = False
            for part in ('checks', 'setup', 'decls'):
                items = getattr(test, part)
                for i in range(len(items)):
                    candidate = Test(test.family, test.seed, list(test.decls), list(test.setup), list(test.checks),
                                     test.prefix)
                    del getattr(candidate, part)[i]
                    if not candidate.checks:
                        continue
                    kind, detail, _ = self.outcome(candidate, failure.mode)
                    if kind == failure.kind and (kind == 'mismatch' or detail == failure.detail):
                        test, progress = candidate, True
                        break
                if progress:
                    break
        return test

    def save(self, failure: Failure, test: Test, root: Path) -> Path:
        target = root / f'targeted-{failure.test.family}-{failure.kind}-seed{failure.test.seed}-{failure.mode}'
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        (target / 'program.dewy').write_text(test.source())
        (target / 'unshrunk.dewy').write_text(failure.test.source())
        (target / 'expected.out').write_text(test.expected)
        kind, detail, actual = self.outcome(test, failure.mode)
        (target / 'actual.out').write_text(actual)
        flags = ' '.join(self.runner.flags(failure.mode))
        (target / 'info.txt').write_text(
            f'{failure.kind} in {failure.mode}: {failure.detail}\n'
            f'minimized: {kind} ({detail})\n'
            f'reproduce: dewy-core build program.dewy -o program {flags}\n'
            f'regenerate: python3 -m tools.compiler.dewy_fuzz_targeted --families {failure.test.family} '
            f'--seed {failure.test.seed} --count 1\n')
        return target


def parse(stdout: str):
    results, started, position = {}, None, 0
    begin = re.compile(re.escape(MARK) + r'B(\d+)\n')
    while (opened := begin.search(stdout, position)) is not None:
        index = int(opened[1])
        started = index
        end = stdout.find(f'{MARK}E{index}\n', opened.end())
        if end < 0:
            break
        results[index] = stdout[opened.end():end]
        position = end
    return results, started


def fuzz(compiler: Path, *, seed: int = 1, count: int | None = None, minutes: float | None = None,
         modes=MODES, families=tuple(FAMILIES), workers: int = 2, batch_size: int = 24, shrink: int = 6,
         failures_dir: Path = FAILURES, quiet: bool = False, work: Path = SCRATCH) -> int:
    started = time.monotonic()
    if count is None and minutes is None:
        count = 100
    deadline = started + minutes * 60 if minutes is not None else None
    work.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='targeted-', dir=work))
    fuzzer = Fuzzer(compiler, modes, scratch)
    failures: list[Failure] = []
    tests = 0
    number = seed
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        while (count is None or number < seed + count) and (deadline is None or time.monotonic() < deadline):
            last = number + batch_size if count is None else min(number + batch_size, seed + count)
            batch = [make(families_for(s, families), s, f't{s}_') for s in range(number, last)]
            tests += len(batch)
            number = last
            for future in [pool.submit(fuzzer.run_batch, batch, mode) for mode in modes]:
                failures += future.result()
            if not quiet:
                print(f'targeted fuzz: seeds {seed}..{number - 1}, {len(failures)} failure(s), '
                      f'{time.monotonic() - started:.0f} s', file=sys.stderr, flush=True)
    finally:
        pool.shutdown()
    groups: dict[tuple, list[Failure]] = {}
    for f in failures:
        groups.setdefault((f.test.family, f.test.seed, f.kind), []).append(f)
    saved = []
    for i, group in enumerate(groups.values()):
        group.sort(key=lambda f: modes.index(f.mode))
        failure = group[0]
        test = fuzzer.shrink(failure) if i < shrink and failure.kind != 'batch-only' else failure.test
        path = fuzzer.save(failure, test, failures_dir)
        saved.append(path)
        print(f'targeted fuzz: {failure.kind} {failure.test.name} in {" ".join(f.mode for f in group)}: '
              f'{failure.detail} -> {path}', flush=True)
    print(f'targeted fuzz: {tests} tests from seed {seed}, {len(modes)} modes, {fuzzer.runner.builds} builds: '
          f'{len(groups)} failure(s) in {time.monotonic() - started:.0f} s', flush=True)
    shutil.rmtree(scratch, ignore_errors=True)
    return 1 if failures else 0


def arguments(argv):
    cli = argparse.ArgumentParser(prog='python3 -m tools.compiler.dewy_fuzz_targeted', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--seed', type=int, default=1, help='first seed (default 1)')
    cli.add_argument('--count', type=int, help='number of tests (default 100 unless --minutes is given)')
    cli.add_argument('--minutes', type=float, help='stop starting new batches after this long')
    cli.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    cli.add_argument('--families', nargs='+', choices=tuple(FAMILIES), default=list(FAMILIES))
    cli.add_argument('-n', '--workers', type=int, default=2, help='parallel builds/runs (default 2)')
    cli.add_argument('--batch', type=int, default=24, help='tests compiled together per build (default 24)')
    cli.add_argument('--shrink', type=int, default=6, help='distinct failures to minimize (default 6)')
    cli.add_argument('--work', type=Path, default=SCRATCH, help='scratch directory for builds and runs')
    cli.add_argument('--failures', type=Path, default=FAILURES, help=f'failure directory (default {FAILURES})')
    cli.add_argument('--compiler', type=Path, help='use this compiler instead of the cached build')
    cli.add_argument('--print', dest='show', action='store_true', help="print each seed's test and oracle output")
    cli.add_argument('-q', '--quiet', action='store_true', help='only the summary line')
    return cli.parse_args(argv)


def main(argv=None, compiler: Path | None = None) -> int:
    options = arguments(argv)
    if options.show:
        for s in range(options.seed, options.seed + (options.count or 1)):
            test = make(families_for(s, options.families), s)
            print(f'# {test.name}\n{test.source()}# oracle output:\n{test.expected}', end='')
        return 0
    compiler = options.compiler or compiler
    if compiler is None:
        from tools import core
        compiler = core.toolchain()
    try:
        return fuzz(Path(compiler).resolve(), seed=options.seed, count=options.count, minutes=options.minutes,
                    modes=tuple(options.modes), families=tuple(options.families), workers=options.workers,
                    batch_size=options.batch, shrink=options.shrink,
                    failures_dir=options.failures.expanduser().resolve(), quiet=options.quiet,
                    work=options.work.expanduser().resolve())
    except RuntimeError as error:
        print(f'targeted fuzz: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
