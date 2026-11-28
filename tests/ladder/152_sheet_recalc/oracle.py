"""Independent spreadsheet recalculation over the same input; run with --write to refresh expected.out."""
from fractions import Fraction
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).parent
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class Bad(Exception):
    pass


class Fault:
    def __init__(self, code):
        self.code = code


def command_line():
    return json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']


def cell(text):
    m = re.fullmatch(r'([A-Z])([1-9][0-9]*)', text)
    if not m or int(m[2]) > 99:
        return None
    return (LETTERS.index(m[1]), int(m[2]))


def name(c):
    return f'{LETTERS[c[0]]}{c[1]}'


def number_text(text):
    if re.fullmatch(r'\d+(\.\d+)?|\d+/[1-9]\d*', text):
        return Fraction(text)
    return None


def lex(text):
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        start = i
        if ch.isdigit() or ch == '.':
            while i < len(text) and (text[i].isdigit() or text[i] == '.'):
                i += 1
        elif ch.isalpha():
            while i < len(text) and text[i].isalnum():
                i += 1
        elif ch in '<>' and i + 1 < len(text) and (text[i + 1] == '=' or text[i:i + 2] == '<>'):
            i += 2
        elif ch in '+-*/(),:<>=':
            i += 1
        else:
            raise Bad(f'unexpected `{ch}`')
        out.append(text[start:i])
    return out


def shown(t):
    return 'the end' if t == '' else f'`{t}`'


STRENGTH = {'<': 1, '>': 1, '=': 1, '<=': 1, '>=': 1, '<>': 1, '+': 2, '-': 2, '*': 3, '/': 3}


class Parser:
    def __init__(self, tokens):
        self.tokens, self.at = tokens, 0

    def peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else ''

    def take(self):
        t = self.peek()
        self.at += 1
        return t

    def expression(self, floor=1):
        left = self.unary()
        while STRENGTH.get(self.peek(), 0) >= floor:
            op = self.take()
            left = ('bin', op, left, self.expression(STRENGTH[op] + 1))
        return left

    def unary(self):
        if self.peek() == '-':
            self.take()
            return ('neg', self.unary())
        return self.primary()

    def primary(self):
        t = self.take()
        if t == '(':
            inner = self.expression()
            if self.take() != ')':
                raise Bad('expected `)`')
            return inner
        n = number_text(t)
        if n is not None:
            return ('num', n)
        if t == '' or not t.isalnum():
            raise Bad(f'expected a value, found {shown(t)}')
        if self.peek() == '(':
            self.take()
            args = []
            while self.peek() != ')':
                if args and self.take() != ',':
                    raise Bad(f'expected `,` or `)` in {t}')
                args.append(self.expression())
            self.take()
            return ('call', t.upper(), args)
        first = cell(t)
        if first is None:
            raise Bad(f'{t} is not a cell')
        if self.peek() != ':':
            return ('ref', first)
        self.take()
        closing = self.take()
        last = cell(closing)
        if last is None:
            raise Bad(f'{shown(closing)} does not end a range')
        return ('span', first, last)


def parse_content(text):
    if text.startswith("'"):
        return text[1:]
    if not text.startswith('='):
        n = number_text(text)
        if n is None:
            raise Bad(f'`{text}` is not a number, \'text or =formula')
        return n
    p = Parser(lex(text[1:]))
    tree = p.expression()
    if p.at < len(p.tokens):
        raise Bad(f'unexpected {shown(p.peek())}')
    return ('formula', tree)


def is_formula(content):
    return isinstance(content, tuple)


def cells_in(first, last):
    return [(col, row) for row in range(min(first[1], last[1]), max(first[1], last[1]) + 1)
            for col in range(min(first[0], last[0]), max(first[0], last[0]) + 1)]


def refs(e):
    kind = e[0]
    if kind == 'ref':
        return [e[1]]
    if kind == 'span':
        return cells_in(e[1], e[2])
    if kind == 'neg':
        return refs(e[1])
    if kind == 'bin':
        return refs(e[2]) + refs(e[3])
    if kind == 'call':
        return [c for a in e[2] for c in refs(a)]
    return []


def half_away(q):
    whole = abs(q.numerator) * 2 + q.denominator
    r = whole // (2 * q.denominator)
    return r if q >= 0 else -r


class Sheet:
    def __init__(self):
        self.contents, self.values = {}, {}

    def value(self, c):
        return self.values.get(c, Fraction(0))

    def number(self, v):
        if isinstance(v, (Fault, Fraction)):
            return v
        return Fault('#VALUE!')

    def numbers(self, args):
        found = []
        for a in args:
            if a[0] == 'span':
                for c in cells_in(a[1], a[2]):
                    v = self.values.get(c)
                    if isinstance(v, Fault):
                        return v
                    if isinstance(v, Fraction):
                        found.append(v)
            else:
                v = self.number(self.eval(a))
                if isinstance(v, Fault):
                    return v
                found.append(v)
        return found

    def eval(self, e):
        kind = e[0]
        if kind == 'num':
            return e[1]
        if kind == 'ref':
            return self.value(e[1])
        if kind == 'span':
            return Fault('#VALUE!')
        if kind == 'neg':
            v = self.number(self.eval(e[1]))
            return v if isinstance(v, Fault) else -v
        if kind == 'bin':
            x = self.number(self.eval(e[2]))
            if isinstance(x, Fault):
                return x
            y = self.number(self.eval(e[3]))
            if isinstance(y, Fault):
                return y
            op = e[1]
            if op == '/':
                return Fault('#DIV/0!') if y == 0 else x / y
            ops = {'+': lambda: x + y, '-': lambda: x - y, '*': lambda: x * y,
                   '<': lambda: Fraction(int(x < y)), '>': lambda: Fraction(int(x > y)),
                   '=': lambda: Fraction(int(x == y)), '<=': lambda: Fraction(int(x <= y)),
                   '>=': lambda: Fraction(int(x >= y)), '<>': lambda: Fraction(int(x != y))}
            return ops[op]()
        return self.call(e[1], e[2])

    def call(self, fn, args):
        if not args:
            return Fault('#ARGS!')
        if fn == 'IF':
            if len(args) != 3:
                return Fault('#ARGS!')
            test = self.number(self.eval(args[0]))
            if isinstance(test, Fault):
                return test
            return self.eval(args[1] if test != 0 else args[2])
        if fn == 'ROUND':
            if len(args) != 2:
                return Fault('#ARGS!')
            x = self.number(self.eval(args[0]))
            if isinstance(x, Fault):
                return x
            places = self.number(self.eval(args[1]))
            if isinstance(places, Fault):
                return places
            if places < 0 or places > 6 or places.denominator != 1:
                return Fault('#VALUE!')
            scale = 10 ** places.numerator
            return Fraction(half_away(x * scale), scale)
        if fn in ('SUM', 'AVG', 'MIN', 'MAX', 'COUNT', 'ABS'):
            if fn == 'ABS' and len(args) != 1:
                return Fault('#ARGS!')
            ns = self.numbers(args)
            if isinstance(ns, Fault):
                return ns
            if fn == 'SUM':
                return sum(ns, Fraction(0))
            if fn == 'COUNT':
                return Fraction(len(ns))
            if fn == 'ABS':
                return abs(ns[0]) if ns else Fraction(0)
            if fn == 'AVG':
                return Fault('#DIV/0!') if not ns else sum(ns, Fraction(0)) / len(ns)
            if not ns:
                return Fraction(0)
            return min(ns) if fn == 'MIN' else max(ns)
        return Fault('#NAME?')

    def order(self):
        position = lambda c: c[1] * 26 + c[0]
        waiting, users = {}, {}
        for c, content in self.contents.items():
            if not is_formula(content):
                continue
            deps = list(dict.fromkeys(d for d in refs(content[1]) if is_formula(self.contents.get(d))))
            waiting[c] = len(deps)
            for d in deps:
                users.setdefault(d, []).append(c)
        ready = sorted((c for c, n in waiting.items() if n == 0), key=position)
        done = []
        while ready:
            nxt = ready.pop(0)
            done.append(nxt)
            for user in users.get(nxt, []):
                waiting[user] -= 1
                if waiting[user] == 0:
                    ready = sorted(ready + [user], key=position)
        stuck = sorted((c for c in waiting if c not in done), key=position)
        return done, stuck

    def recalc(self, dirty):
        ready, stuck = self.order()
        count = 0
        for c in ready:
            if dirty is not None and c not in dirty:
                continue
            self.values[c] = self.eval(self.contents[c][1])
            count += 1
        for c in stuck:
            if dirty is not None and c not in dirty:
                continue
            self.values[c] = Fault('#CYCLE!')
            count += 1
        return count

    def set(self, c, content):
        self.contents[c] = content
        if not is_formula(content):
            self.values[c] = content

    def reached(self, changed):
        seen, frontier = set(changed), list(changed)
        while frontier:
            nxt = []
            for c, content in self.contents.items():
                if not is_formula(content) or c in seen:
                    continue
                if any(d in frontier for d in refs(content[1])):
                    seen.add(c)
                    nxt.append(c)
            frontier = nxt
        return seen


def show(v):
    if isinstance(v, Fault):
        return v.code
    if isinstance(v, str):
        return v
    if v.denominator == 1:
        return str(v.numerator)
    cents = half_away(v * 100)
    sign = '-' if cents < 0 else ''
    return f'{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}'


def grid(sheet, out):
    if not sheet.contents:
        return
    last_row = max(c[1] for c in sheet.contents)
    cols = sorted({c[0] for c in sheet.contents})
    widths = [max([1] + [len(show(sheet.value(c))) for c in sheet.contents if c[0] == col]) for col in cols]

    def center(text, w):
        pad = max(0, w - len(text))
        return ' ' * (pad // 2) + text + ' ' * (pad - pad // 2)
    out.append('   |' + '|'.join(center(LETTERS[col], w) for col, w in zip(cols, widths)))
    for row in range(1, last_row + 1):
        parts = []
        for col, w in zip(cols, widths):
            c = (col, row)
            if c not in sheet.contents:
                parts.append(' ' * w)
                continue
            v = sheet.value(c)
            parts.append(show(v).rjust(w) if isinstance(v, Fraction) else show(v).ljust(w))
        out.append(f'{row:>3}|' + '|'.join(parts))


def run(argv, text):
    out = []
    sheet = Sheet()
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            out.append(f'line {n}: expected `CELL: content`')
            continue
        head, rest = line.split(':', 1)
        c = cell(head.strip())
        if c is None:
            out.append(f'line {n}: `{head.strip()}` is not a cell')
            continue
        try:
            sheet.set(c, parse_content(rest.strip()))
        except Bad as bad:
            out.append(f'line {n}: {name(c)}: {bad}')
    out.append(f'calculated {sheet.recalc(None)} formulas')
    grid(sheet, out)
    faults = [f'{name(c)} {v.code}' for c, v in sheet.values.items() if isinstance(v, Fault)]
    if faults:
        out.append('errors: ' + ', '.join(faults))
    for edit in argv[1:]:
        if ':' not in edit:
            out.append(f'edit `{edit}`: expected CELL:content')
            continue
        head, rest = edit.split(':', 1)
        c = cell(head)
        if c is None:
            out.append(f'edit `{edit}`: not a cell')
            continue
        try:
            content = parse_content(rest)
        except Bad as bad:
            out.append(f'edit {name(c)}: {bad}')
            continue
        before = dict(sheet.values)
        sheet.set(c, content)
        dirty = sheet.reached([c])
        count = sheet.recalc(dirty)
        shown_at = lambda values, d: show(values.get(d, ''))
        moved = [f'{name(d)} {shown_at(before, d)} -> {shown_at(sheet.values, d)}'
                 for d in sorted(dirty, key=lambda d: d[1] * 26 + d[0])
                 if shown_at(before, d) != shown_at(sheet.values, d)]
        out.append(f'set {edit}: recalculated {count}, changed {", ".join(moved) if moved else "nothing"}')
    if len(argv) > 1:
        grid(sheet, out)
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    result = run(['sheet_recalc'] + command_line(), (HERE / 'stdin.txt').read_text())
    if sys.argv[1:] == ['--write']:
        expected.write_text(result)
    elif expected.read_text() != result:
        sys.exit('expected.out differs from the recalculated sheet')
