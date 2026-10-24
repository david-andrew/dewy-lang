"""compiler/dewy_syntax.dewy (the Dewy frontend's syntax tree: a node's children, the reading
an ambiguous node takes, the operator a node applies, the kind names, and the `$target` and
`$build` conditions that fold): it ships, and its frozen implementation-language twin
compiler/dewy_syntax.jo gives the same answers. One Sloppy driver runs over either module on
random trees; the oracle below follows the rules, stopping at the first mistake."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_syntax_jo.jo'
ENUMS = dewy_enumerations((ROOT / 'compiler/dewy_tokens.dewy').read_text())
KINDS, TOKENS = ENUMS['DewyKind'], ENUMS['DewyToken']
NAMES = ['x86_64', 'riscv64', 'aarch64', 'c', 'x86_64-freestanding', 'riscv64-freestanding',
         'aarch64-freestanding', 'c-freestanding', 'x86_64-linux', 'riscv64-linux', 'aarch64-linux',
         'c-linux', 'x86_64-mac', 'aarch64-mac', 'x86_64-windows', 'riscv64-windows', 'aarch64-windows',
         'c-windows', 'c-posix', 'c89', 'wasm32']
ARCHES = ['x86_64', 'riscv64', 'aarch64', 'c', 'wasm32']
OSES = ['linux', 'mac', 'windows', 'freestanding', 'posix', 'none']
SHOWN = {'unknown': 'Unknown', 'identifier': 'Identifier', 'boolean': 'Bool', 'metatag': 'Metatag',
         'based_string': 'BasedString', 'integer': 'Integer', 'source_integer': 'Integer',
         'source_real': 'Real', 'atom': 'Atom', 'ambiguous': 'Ambiguous', 'binary': 'BinOp',
         'block': 'Block', 'combined_assignment': 'CombinedAssignmentOp', 'flat': 'Flat', 'flow': 'Flow',
         'interpolated_string': 'IString', 'inverted_comparison': 'InvertedComparisonOp',
         'keyword': 'Keyword', 'keyword_expr': 'KeywordExpr', 'operator': 'Operator', 'postfix': 'Postfix',
         'prefix': 'Prefix', 'string': 'String', 'string_chunk': 'StringChunk', 'directive': 'Directive',
         'compact_expr': 'CompactExpression', 'compact_stmt': 'CompactStatement', 'lazy_body': 'LazyBody'}
COMBINED = {'+': 'plus_assign', '-': 'minus_assign', '*': 'star_assign', '//': 'floor_assign', '?': 'none'}
AMBIGUOUS = 'an ambiguous expression; use explicit multiplication or parentheses'


class Mistake(Exception):
    def __init__(self, at, message, unsupported=False):
        super().__init__(message)
        self.at, self.message, self.unsupported = at, message, unsupported


class Node:
    def __init__(self, kind, text='', symbol='none', children=(), inline=None):
        self.kind, self.text, self.symbol = kind, text, symbol
        self.children = list(children)
        self.inline = inline     # (sentinel, left, right) kept in place of children


def arch_of(name):
    return 'c' if name == 'c89' else name.split('-', 1)[0]


def os_of(name):
    return name.split('-', 1)[1] if '-' in name else 'none'


class Oracle:
    def __init__(self, tree):
        self.t = tree

    def pos(self, i):
        return i * 10 + 1

    def kids(self, i):
        n = self.t[i]
        return list(n.inline) if n.inline else n.children

    def mult(self, i):
        return (self.t[i].text == 'MultiplyJuxtapose') + sum(self.mult(c) for c in self.kids(i))

    def unwrap(self, i):
        """the node, or ('tie', ambiguous node)"""
        while True:
            n = self.t[i]
            if n.kind == 'atom':
                i = self.kids(i)[0]
            elif n.kind == 'ambiguous':
                scores = [self.mult(c) for c in self.kids(i)]
                if not scores or scores.count(min(scores)) > 1:
                    return ('tie', i)
                i = self.kids(i)[scores.index(min(scores))]
            else:
                return i

    def unwrapped(self, i):
        u = self.unwrap(i)
        if isinstance(u, tuple):
            raise Mistake(self.pos(u[1]), AMBIGUOUS, True)
        return u

    def op(self, u):
        n = self.t[u]
        if n.kind not in ('binary', 'prefix', 'postfix', 'flat'):
            return 'none'
        if n.symbol != 'none':
            return n.symbol
        first = self.t[self.kids(u)[0]]
        if n.kind == 'binary' and first.kind == 'combined_assignment':
            return COMBINED[self.t[self.kids(self.kids(u)[0])[0]].text]
        return first.symbol

    def metatag(self, i, name):
        n = self.t[self.unwrapped(i)]
        return n.kind == 'metatag' and n.text == name

    def name(self, i):
        n = self.t[self.unwrapped(i)]
        return n.text if n.kind == 'identifier' else ''

    def field(self, i):
        i = self.unwrapped(i)
        if self.metatag(i, 'target'):
            return 0
        if self.op(i) != 'dot' or len(self.kids(i)) != 3:
            return -1
        _, left, right = self.kids(i)
        member = self.name(right)
        if self.metatag(left, 'build'):
            if member == 'mode':
                return 3
            if member == 'debug':
                raise Mistake(self.pos(i), "`$build` has `mode` ('debug' or 'release'), not `debug`: test `$build.mode =? 'debug'`")
            raise Mistake(self.pos(i), f"`$build` has `mode` ('debug' or 'release'), not `{member}`")
        if not self.metatag(left, 'target'):
            return -1
        return {'arch': 1, 'os': 2}.get(member, -1)

    def literal(self, i, field):
        i = self.unwrapped(i)
        if self.t[i].kind != 'string':
            return ''
        name, at = self.t[i].text, self.pos(i)
        if field == 3:
            if name not in ('release', 'debug'):
                raise Mistake(at, f'unknown build mode "{name}": `$build.mode` is "release" or "debug"')
        elif field == 1:
            if name not in ARCHES:
                raise Mistake(at, f'unknown processor "{name}": `$target.arch` is one of {", ".join(ARCHES)}')
        elif field == 2:
            if name not in OSES:
                raise Mistake(at, f'unknown system "{name}": `$target.os` is one of {", ".join(OSES)}')
        elif name not in NAMES:
            raise Mistake(at, f'unknown target "{name}": `$target` is one of {", ".join(NAMES)}')
        elif os_of(name) == 'none' and name not in ('wasm32', 'c89'):
            raise Mistake(at, f'`$target` is a full target name, never "{name}" alone (which asks for the current machine): '
                              f'test the processor with `$target.arch =? "{name}"`, or name the system too, as "{name}-linux"')
        return name

    @staticmethod
    def value(field, target, mode):
        return [target, arch_of(target), os_of(target), mode][field] if 0 <= field <= 3 else target

    def fold(self, i, target, mode):
        """True, False or None (no such condition)"""
        i = self.unwrapped(i)
        n = self.t[i]
        if n.kind == 'block' and n.text == '():' and len(self.kids(i)) == 1:
            return self.fold(self.kids(i)[0], target, mode)
        op = self.op(i)
        if n.kind == 'prefix' and op == 'kw_not':
            inner = self.fold(self.kids(i)[1], target, mode)
            return None if inner is None else not inner
        if n.kind != 'binary':
            return None
        sentinel, left, right = self.kids(i)[:3]
        if op in ('kw_and', 'kw_or'):
            a = self.fold(left, target, mode)
            if a is None:
                return None
            b = self.fold(right, target, mode)
            if b is None:
                return None
            return (a and b) if op == 'kw_and' else (a or b)
        inverted = self.t[sentinel].kind == 'inverted_comparison' or op in ('not_eq', 'not_contains')
        if op in ('eq', 'not_eq'):
            if self.field(right) >= 0:
                left, right = right, left
            field = self.field(left)
            if field < 0:
                return None
            name = self.literal(right, field)
            if not name:
                return None
            found = name == self.value(field, target, mode)
        elif op in ('contains', 'not_contains'):
            field = self.field(left)
            if field < 0:
                return None
            items = self.unwrapped(right)
            if self.t[items].kind != 'block' or self.t[items].text != '[]:':
                return None
            found = False
            for entry in self.kids(items):
                name = self.literal(entry, field)
                if not name:
                    return None
                found = found or name == self.value(field, target, mode)
        else:
            return None
        return found != inverted

    def live(self, i, target, mode):
        i = self.unwrapped(i)
        if self.t[i].kind != 'flow':
            return -1
        for arm in self.kids(i):
            if self.t[arm].kind != 'keyword_expr':
                return arm
            ks = self.kids(arm)
            if self.t[ks[0]].text != 'if' or len(ks) != 3:
                return -1
            f = self.fold(ks[1], target, mode)
            if f is None:
                return -1
            if f:
                return ks[2]
        return 0

    def setting_place(self, i):
        i = self.unwrapped(i)
        if self.metatag(i, 'target') or self.metatag(i, 'build'):
            return True
        if self.op(i) != 'dot' or len(self.kids(i)) != 3:
            return False
        left = self.kids(i)[1]
        return self.metatag(left, 'build') or self.metatag(left, 'target')

    def setting_text(self, i):
        i = self.unwrapped(i)
        if self.metatag(i, 'target'):
            return '$target'
        if self.metatag(i, 'build'):
            return '$build'
        base = '$build' if self.metatag(self.kids(i)[1], 'build') else '$target'
        return f'{base}.{self.name(self.kids(i)[2])}'

    def answer(self, f):
        try:
            v = f()
        except Mistake as m:
            return f'! {m.at} {str(m.unsupported).lower()} {m.message}'
        return str(v).lower() if isinstance(v, bool) else str(v)


class Trees:
    """random trees of the shapes the parser makes, `$target` conditions among them"""

    def __init__(self, rng):
        self.rng = rng
        self.t = [Node('unknown'), Node('inverted_comparison')]

    def add(self, node):
        self.t.append(node)
        return len(self.t) - 1

    def operator(self, kind, symbol, operands, inverted=False):
        r = self.rng.random()
        sentinel = 1 if inverted else 0
        if kind == 'binary' and r < 0.5:
            return self.add(Node(kind, inline=(sentinel, *operands)))
        if r < 0.8:
            return self.add(Node(kind, symbol=symbol, children=[sentinel, *operands]))
        # (the operator a child node)
        first = self.add(Node('operator', symbol=symbol))
        return self.add(Node(kind, children=[first, *operands]))

    def fix_inline(self, i, symbol):
        n = self.t[i]
        if n.inline:
            n.symbol = symbol
        return i

    def leaf(self):
        r = self.rng
        pick = r.random()
        if pick < 0.2:
            return self.add(Node('metatag', r.choice(['target', 'target', 'build', 'build', 'supported_targets'])))
        if pick < 0.3:
            return self.add(Node('identifier', r.choice(['arch', 'os', 'mode', 'debug', 'name', ''])))
        if pick < 0.6:
            return self.field()
        if pick < 0.85:
            return self.text()
        if pick < 0.95:
            return self.add(Node('block', '[]:', children=[self.text() for _ in range(r.randrange(4))]))
        return self.add(Node(r.choice(['integer', 'keyword', 'string_chunk']), r.choice(['1', 'if', 'x86_64'])))

    def text(self):
        r = self.rng
        name = r.choice(NAMES + ARCHES + OSES + ['debug', 'release', 'bogus', 'x86_64-linux ', 'Linux'])
        return self.wrap(self.add(Node('string', name)))

    def field(self):
        r = self.rng
        base = self.add(Node('metatag', r.choice(['target', 'target', 'build', 'cfg'])))
        if r.random() < 0.2:
            return self.wrap(base)
        member = self.add(Node('identifier', r.choice(['arch', 'os', 'mode', 'mode', 'debug', 'cpu'])))
        if r.random() < 0.1:
            return self.add(Node('flat', symbol='dot', children=[0, base]))
        return self.wrap(self.fix_inline(self.operator('binary', 'dot', [self.wrap(base), self.wrap(member)]), 'dot'))

    def wrap(self, i):
        r = self.rng.random()
        if r < 0.08:
            return self.add(Node('atom', children=[i]))
        if r < 0.12:
            return self.add(Node('block', '():', children=[i]))
        if r < 0.18:
            # (an ambiguous node: its readings, one of them i, the others making k multiplications)
            readings = [i]
            for _ in range(self.rng.randrange(1, 3)):
                k = self.rng.randrange(3)
                j = self.add(Node('identifier', 'n'))
                for _ in range(k):
                    j = self.add(Node('keyword', 'MultiplyJuxtapose', children=[j]))
                readings.append(j)
            self.rng.shuffle(readings)
            return self.add(Node('ambiguous', children=readings))
        return i

    def condition(self, depth):
        r = self.rng
        pick = r.random()
        if depth <= 0 or pick < 0.45:
            op = r.choice(['eq', 'eq', 'not_eq', 'contains', 'not_contains', 'lt'])
            a, b = self.field(), self.leaf()
            if r.random() < 0.3:
                a, b = b, a
            return self.wrap(self.fix_inline(self.operator('binary', op, [a, b], inverted=r.random() < 0.2), op))
        if pick < 0.6:
            return self.wrap(self.operator('prefix', r.choice(['kw_not', 'kw_not', 'minus']), [self.condition(depth - 1)]))
        if pick < 0.9:
            op = r.choice(['kw_and', 'kw_or'])
            return self.wrap(self.fix_inline(self.operator('binary', op, [self.condition(depth - 1), self.condition(depth - 1)]), op))
        if pick < 0.95:
            # (a combined assignment's operator: never a condition)
            spelled = self.add(Node('operator', r.choice(list(COMBINED))))
            first = self.add(Node('combined_assignment', children=[spelled]))
            return self.add(Node('binary', children=[first, self.field(), self.leaf()]))
        return self.leaf()

    def flow(self):
        r = self.rng
        arms = []
        for _ in range(r.randrange(1, 4)):
            word = self.add(Node('keyword', r.choice(['if', 'if', 'if', 'loop'])))
            body = self.add(Node('block', '{}:', children=[self.leaf()]))
            parts = [word, self.condition(2), body][:3 if r.random() < 0.95 else 2]
            arms.append(self.add(Node('keyword_expr', children=parts)))
        if r.random() < 0.4:
            arms.append(self.add(Node('block', '{}:', children=[self.leaf()])))
        return self.add(Node('flow', children=arms))

    def setting(self):
        place = self.field() if self.rng.random() < 0.8 else self.leaf()
        return self.fix_inline(self.operator('binary', 'assign', [place, self.text()]), 'assign')


def corpus():
    rng = random.Random(13)
    lines = []
    want = []
    settings = [('x86_64-linux', 'debug'), ('aarch64-mac', 'release'), ('wasm32', 'debug'), ('x86_64-windows', 'release')]
    for kind in range(len(KINDS)):
        lines.append(f'Q\tkind\t{kind}')
        want.append(SHOWN.get(KINDS[kind], KINDS[kind]))
    for target in NAMES:
        for field in range(5):
            for mode in ('debug', 'release'):
                lines.append(f'Q\tvalue\t{field}\t{target}\t{mode}')
                want.append(Oracle.value(field, target, mode))
    for _ in range(160):
        trees = Trees(rng)
        roots = [trees.condition(3) for _ in range(3)] + [trees.flow(), trees.setting(), trees.field()]
        lines.append('T')
        for n in trees.t:
            sentinel, left, right = (n.inline[0] + 1, n.inline[1], n.inline[2]) if n.inline else (0, 0, 0)
            lines.append('\t'.join(['N', str(KINDS.index(n.kind)), n.text, str(TOKENS.index(n.symbol)),
                                    str(sentinel), str(left), str(right), ','.join(map(str, n.children))]))
        o = Oracle(trees.t)
        for i in range(2, len(trees.t)):
            n = trees.t[i]
            ks = o.kids(i)
            lines.append(f'Q\tshape\t{i}')
            want.append(f'{len(ks)} {",".join(map(str, ks))} {len(ks)} {o.mult(i)}')
            u = o.unwrap(i)
            lines.append(f'Q\tunwrap\t{i}')
            want.append(str(-1 - u[1]) if isinstance(u, tuple) else f'{u} {o.op(u)}')
            for what, f in [('field', lambda: o.field(i)), ('place', lambda: o.setting_place(i))]:
                lines.append(f'Q\t{what}\t{i}')
                want.append(o.answer(f))
            for field in range(4):
                lines.append(f'Q\tliteral\t{i}\t{field}')
                want.append(o.answer(lambda: o.literal(i, field)))
            ok = o.answer(lambda: o.setting_place(i))
            if ok == 'true' or ok == 'false' and o.op(o.unwrapped(i)) == 'dot' and len(o.kids(o.unwrapped(i))) == 3:
                lines.append(f'Q\ttext\t{i}')
                want.append(o.answer(lambda: o.setting_text(i)))
        for i in roots:
            for target, mode in settings:
                lines.append(f'Q\tcondition\t{i}\t{target}\t{mode}')
                want.append(o.answer(lambda: {True: 1, False: 0, None: -1}[o.fold(i, target, mode)]))
                lines.append(f'Q\tlive\t{i}\t{target}\t{mode}')
                want.append(o.answer(lambda: o.live(i, target, mode)))
    return '\n'.join(lines) + '\n', ''.join(w + '\n' for w in want)


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def test_corpus_reaches_every_answer():
    _, want = corpus()
    answers = want.split('\n')
    assert sum(a.startswith('! ') and 'ambiguous' in a for a in answers) > 20
    for text in ['unknown build mode', 'unknown processor', 'unknown system', 'unknown target',
                 'full target name', 'not `debug`', 'not `cpu`']:
        assert sum(text in a for a in answers) > 5, text
    assert {'1', '0', '-1', 'true', 'false', '$build.mode', '$target.arch'} <= set(answers)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_syntax_match_jo(compiler, tmp_path, release):
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/dewy_syntax.jo'"
    assert twin in driver
    text, want = corpus()
    questions = tmp_path / 'trees'
    questions.write_text(text)
    outputs = []
    for module in ('dewy_syntax.dewy', 'dewy_syntax.jo'):
        source = tmp_path / f'driver-{module.replace(".", "-")}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'").replace("use '../../../", f"use '{ROOT}/"))
        binary = build(compiler, source, tmp_path / source.stem, release)
        ran = subprocess.run([binary, questions], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    for got, expected in zip(outputs[0].split('\n'), want.split('\n')):
        assert got == expected
    assert outputs[0] == want


@pytest.mark.core_quick
def test_selfhost_dewy_syntax_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_syntax.dewy\0' in binary
    assert b'/compiler/dewy_syntax.jo\0' not in binary
    main = tmp_path / 'main.dewy'
    main.write_text("main=():>void=>{\n"
                    "    if not ($target.os =? 'windows') and $target.arch in? ['x86_64' 'aarch64'] {printl('a')} else {printl('b')}\n"
                    "    if $build.mode =? 'release' {printl('r')} else {printl($build.mode)}\n"
                    "}\n")
    ran = subprocess.run([compiler, 'run', main], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0 and ran.stdout == 'a\ndebug\n', ran.stdout + ran.stderr
    main.write_text("main=():>void=>{\n    if $target.os =? 'linx' {printl(1)}\n}\n")
    checked = subprocess.run([compiler, 'check', main], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0
    assert ':2:22: error: unknown system "linx": `$target.os` is one of' in checked.stdout + checked.stderr
