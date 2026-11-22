"""Independent calculator over stdin.txt; run with --write to refresh expected.out."""
from pathlib import Path
import re
import sys

HERE = Path(__file__).parent
KEYWORDS = {'let', 'def', 'if', 'then', 'else', 'true', 'false'}
OPERATORS = ['==', '!=', '<=', '>=', '<', '>', '+', '-', '*', '/', '%', '(', ')', ',', '=']
STRENGTH = {'==': 1, '!=': 1, '<': 1, '<=': 1, '>': 1, '>=': 1, '+': 2, '-': 2, '*': 3, '/': 3, '%': 3}
MAX_DEPTH = 200


class Fail(Exception):
    def __init__(self, col, message):
        self.col, self.message = col, message


def lex(line):
    tokens, i = [], 0
    while i < len(line):
        ch, col = line[i], i + 1
        if ch.isspace():
            i += 1
        elif ch.isalnum() or ch == '_':
            m = re.compile(r'[\w]+').match(line, i)
            text = m.group()
            i = m.end()
            kind = 'num' if ch.isdigit() else 'keyword' if text in KEYWORDS else 'name'
            if kind == 'num' and not text.isdigit():
                raise Fail(col, f'malformed number {text}')
            tokens.append((kind, text, col))
        else:
            text = line[i:i + 2] if line[i:i + 2] in OPERATORS else ch
            if text not in OPERATORS:
                raise Fail(col, f"unexpected character '{ch}'")
            tokens.append(('op', text, col))
            i += len(text)
    tokens.append(('end', '', len(line) + 1))
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens, self.at = tokens, 0

    def peek(self):
        return self.tokens[self.at]

    def next(self):
        t = self.tokens[self.at]
        self.at = min(self.at + 1, len(self.tokens) - 1)
        return t

    def is_op(self, t, text):
        return t[0] in ('op', 'keyword') and t[1] == text

    def expect(self, text):
        t = self.next()
        if not self.is_op(t, text):
            raise Fail(t[2], f"expected '{text}', found {describe(t)}")

    def expression(self, floor=1):
        left = self.unary()
        while True:
            t = self.peek()
            s = STRENGTH.get(t[1], 0) if t[0] == 'op' else 0
            if s < floor:
                return left
            self.next()
            left = ('bin', t[1], t[2], left, self.expression(s + 1))
            n = self.peek()
            if s == 1 and n[0] == 'op' and STRENGTH.get(n[1]) == 1:
                raise Fail(n[2], 'comparisons do not chain; add parentheses')

    def unary(self):
        t = self.peek()
        if self.is_op(t, '-'):
            self.next()
            return ('neg', t[2], self.unary())
        return self.primary()

    def primary(self):
        t = self.next()
        if t[0] == 'num':
            return ('val', int(t[1]))
        if self.is_op(t, 'true') or self.is_op(t, 'false'):
            return ('val', t[1] == 'true')
        if self.is_op(t, '('):
            inner = self.expression()
            self.expect(')')
            return inner
        if self.is_op(t, 'if'):
            test = self.expression()
            self.expect('then')
            yes = self.expression()
            self.expect('else')
            return ('if', t[2], test, yes, self.expression())
        if t[0] != 'name':
            raise Fail(t[2], f'unexpected {describe(t)}')
        if not self.is_op(self.peek(), '('):
            return ('ref', t[1], t[2])
        self.next()
        args = []
        if not self.is_op(self.peek(), ')'):
            args.append(self.expression())
            while self.is_op(self.peek(), ','):
                self.next()
                args.append(self.expression())
        self.expect(')')
        return ('call', t[1], t[2], args)


def describe(t):
    return 'end of line' if t[0] == 'end' else f"'{t[1]}'"


def show(v):
    return ('true' if v else 'false') if isinstance(v, bool) else str(v)


def number(v, col, what):
    if isinstance(v, bool):
        raise Fail(col, f'{what} needs a number, not {show(v)}')
    return v


class Machine:
    def __init__(self):
        self.globals, self.functions, self.depth = {}, {}, 0

    def eval(self, e, local):
        kind = e[0]
        if kind == 'val':
            return e[1]
        if kind == 'ref':
            if e[1] in local:
                return local[e[1]]
            if e[1] in self.globals:
                return self.globals[e[1]]
            raise Fail(e[2], f'unknown name {e[1]}')
        if kind == 'neg':
            return -number(self.eval(e[2], local), e[1], '-')
        if kind == 'if':
            test = self.eval(e[2], local)
            if not isinstance(test, bool):
                raise Fail(e[1], f'if needs true or false, not {show(test)}')
            return self.eval(e[3] if test else e[4], local)
        if kind == 'bin':
            _, op, col, l, r = e
            a, b = self.eval(l, local), self.eval(r, local)
            if op == '==':
                return type(a) is type(b) and a == b
            if op == '!=':
                return not (type(a) is type(b) and a == b)
            x, y = number(a, col, f"'{op}'"), number(b, col, f"'{op}'")
            if op in ('/', '%') and y == 0:
                raise Fail(col, 'division by zero')
            return {'+': lambda: x + y, '-': lambda: x - y, '*': lambda: x * y, '<': lambda: x < y,
                    '<=': lambda: x <= y, '>': lambda: x > y, '>=': lambda: x >= y,
                    '/': lambda: x // y, '%': lambda: x % y}[op]()
        _, name, col, arg_trees = e
        args = [self.eval(a, local) for a in arg_trees]
        if name in ('abs', 'max', 'min'):
            ns = [number(a, col, name) for a in args]
            if not ns:
                raise Fail(col, f'{name} needs at least one argument')
            if name == 'abs':
                if len(ns) != 1:
                    raise Fail(col, f'abs takes 1 argument, not {len(ns)}')
                return abs(ns[0])
            return max(ns) if name == 'max' else min(ns)
        if name not in self.functions:
            raise Fail(col, f'unknown function {name}')
        params, body = self.functions[name]
        if len(params) != len(args):
            noun = 'argument' if len(params) == 1 else 'arguments'
            raise Fail(col, f'{name} takes {len(params)} {noun}, not {len(args)}')
        if self.depth >= MAX_DEPTH:
            raise Fail(col, f'recursion deeper than {MAX_DEPTH} calls')
        self.depth += 1
        try:
            return self.eval(body, dict(zip(params, args)))
        finally:
            self.depth -= 1

    def line(self, text):
        p = Parser(lex(text))
        first = p.peek()
        if p.is_op(first, 'def'):
            p.next()
            name = p.next()
            if name[0] != 'name':
                raise Fail(name[2], f'expected a function name, found {describe(name)}')
            p.expect('(')
            params = []
            while not p.is_op(p.peek(), ')'):
                if params:
                    p.expect(',')
                param = p.next()
                if param[0] != 'name':
                    raise Fail(param[2], f'expected a parameter name, found {describe(param)}')
                if param[1] in params:
                    raise Fail(param[2], f'parameter {param[1]} appears twice')
                params.append(param[1])
            p.next()
            p.expect('=')
            body = p.expression()
            if p.peek()[0] != 'end':
                raise Fail(p.peek()[2], f'unexpected {describe(p.peek())}')
            self.functions[name[1]] = (params, body)
            return f'defined {name[1]}/{len(params)}'
        target = ''
        if p.is_op(first, 'let'):
            p.next()
            name = p.next()
            if name[0] != 'name':
                raise Fail(name[2], f'expected a name, found {describe(name)}')
            p.expect('=')
            target = name[1]
        tree = p.expression()
        if p.peek()[0] != 'end':
            raise Fail(p.peek()[2], f'unexpected {describe(p.peek())}')
        value = self.eval(tree, {})
        if not target:
            return show(value)
        self.globals[target] = value
        return f'{target} = {show(value)}'


def run(text):
    m, out, ok, failed = Machine(), [], 0, 0
    for number_, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith('#'):
            continue
        try:
            out.append(f'{number_}: {m.line(line)}')
            ok += 1
        except Fail as e:
            out.append(f'{number_}: error at column {e.col}: {e.message}')
            m.depth = 0
            failed += 1
    out.append(f'{ok} lines evaluated, {failed} errors, {len(m.functions)} functions, {len(m.globals)} globals')
    return '\n'.join(out) + '\n'


def main():
    output = run((HERE / 'stdin.txt').read_text())
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(output)
    elif expected.read_text() != output:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    sys.setrecursionlimit(20000)
    main()
