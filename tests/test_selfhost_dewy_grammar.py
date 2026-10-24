"""compiler/dewy_grammar.dewy (the Dewy grammar's rules over the lexemes: how tightly operators
bind and which way they group, comparison chains, where expressions start, juxtaposition,
partial application, directive forms, operator hints, `<<` as two openers and a format spec's
colon): it ships, and its frozen implementation-language twin compiler/dewy_grammar.jo gives the
same answers. One Sloppy driver runs over either module on random lexemes. The oracle checks the
binding powers against docs/LANGUAGE.md's table (their order, not their numbers) and follows the
other rules as docs/design/juxtaposition.md and the language guide state them."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_grammar_jo.jo'
ENUMS = dewy_enumerations((ROOT / 'compiler/dewy_tokens.dewy').read_text())
KINDS, TOKENS = ENUMS['DewyKind'], ENUMS['DewyToken']

COMPARISONS = ['eq', 'not_eq', 'lt', 'not_lt', 'gt', 'not_gt', 'le', 'not_le', 'ge', 'not_ge']
ASSIGNMENTS = [t for t in TOKENS if t.endswith('_assign') and t != 'angle_assign'] + ['assign']
# docs/LANGUAGE.md "Operators bind from tightest to loosest", a row each: its tokens and how it
# groups. Broadcast forms bind like their scalar forms. `ranked` rows are the ones the parser's
# loop compares powers for: the infix rows, and `or_throw`, a postfix a line may start with.
TABLE = [
    (['at'], 'prefix'),
    (['dot', 'call', 'index', 'ellipsis', 'type_apply'], 'postfix'),
    (['tilde', 'no'], 'prefix'),
    (['question'], 'postfix'),
    (['caret', 'dot_caret'], 'right'),
    (['multiply_apply'], 'postfix'),
    (['star', 'slash', 'floor', 'percent', 'dot_star', 'dot_slash', 'dot_floor', 'dot_percent'], 'left'),
    (['+prefix', '-prefix'], 'prefix'),
    (['plus', 'minus', 'dot_plus', 'dot_minus'], 'left'),
    (['shl', 'shr'], 'left'),
    (['comma'], 'flat'),
    (['range'], 'range'),
    (['kw_in'], 'iterator'),
    (['kw_of'], 'prefix'),
    (['amp'], 'left'),
    (['pipe'], 'left'),
    (['coalesce'], 'right'),
    (COMPARISONS + ['dot_' + c for c in COMPARISONS] + ['is_type', 'isnt_type', 'contains', 'not_contains'], 'chain'),
    (['kw_not'], 'prefix'),
    (['kw_and', 'kw_nand'], 'left'),
    (['kw_xor', 'kw_xnor'], 'left'),
    (['kw_or', 'kw_nor'], 'left'),
    (['kw_as', 'kw_transmute'], 'left'),
    (['kw_or_throw'], 'ranked postfix'),
    (['colon'], 'annotation'),
    (['returns'], 'left'),
    (['function'], 'right'),
    (['pipe_right'], 'left'),
    (['pipe_left'], 'right'),
    (['arrow'], 'arrow'),
    (ASSIGNMENTS, 'assignment'),
    (['statement_end'], 'postfix'),
]
ROW = {}
for _row, (_tokens, _grouping) in enumerate(TABLE):
    for _t in _tokens:
        ROW.setdefault(_t, (_row, _grouping))
UNRANKED = {'prefix', 'postfix'}
PREFIXES = {'at': 'at', 'tilde': 'tilde', 'kw_of': 'kw_of', 'kw_not': 'kw_not', 'plus': '+prefix',
            'minus': '-prefix', 'dot_plus': '+prefix', 'dot_minus': '-prefix'}
# (the language guide: a binary operator with its right operand is a function, `(* 2)`,
# `(<? limit)`, `(.x)`; not `+` and `-`, whose prefix meaning wins: `(-1)`)
PARTIAL = set(COMPARISONS) | {'is_type', 'isnt_type', 'contains', 'not_contains', 'dot', 'kw_as', 'kw_transmute',
                               'star', 'slash', 'floor', 'percent', 'caret'}
CHAIN = {'lt': 1, 'le': 1, 'gt': -1, 'ge': -1, 'eq': 0}
CLOSERS = {'rparen', 'rbrack', 'rbrace', 'rangle', 'shr', 'kw_else', 'semi', 'comma'}
STATEMENTS = {'lbrace', 'kw_let', 'kw_const', 'kw_return', 'kw_break', 'kw_continue', 'kw_if', 'kw_loop',
              'kw_parallel', 'kw_match'}
FORMS = {'assert': 1, 'runtime_assert': 1, 'expect': 1, 'unsafe_assume': 1, 'fail': 2, 'breakpoint': 3, 'lend': 4,
         'allocator': 5, 'unsafe': 6, 'warn_if': 7}
DESIGNED = {'abstract', 'field', 'lend', 'no_prelude', 'proof', 'unsafe_assume', '__copy__', '__drop__', '__move__'}
METATAGS = sorted(FORMS) + sorted(DESIGNED) + ['extern', 'export', 'test', 'target', 'build', 'capture', 'Assert', '']
NUMBERS = {'integer', 'source_integer', 'source_real'}
HABIT_TEXTS = ['*', '!', '&', '|', '=', '>', '<', '>=', '<=', '+', '-', '%', 'x']


class Lexeme:
    def __init__(self, kind, symbol='none', space=False, newline=False):
        self.kind, self.symbol, self.space, self.newline = kind, symbol, space, newline


def ranked(t):
    return t in ROW and ROW[t][1] not in UNRANKED


def can_start(ts, at):
    return ts[at].kind != 'eof' and ts[at].symbol not in CLOSERS


def range_bound(ts, at):
    s = ts[at].symbol
    return can_start(ts, at) and s not in STATEMENTS and (not ranked(s) or s in ('plus', 'minus'))


def coefficient_before(ts, at):
    """after a number literal, not a tuple member's index (`t.1`)"""
    if at == 0 or ts[at - 1].kind not in NUMBERS:
        return False
    return not (at >= 2 and ts[at - 2].symbol == 'dot' and not ts[at - 1].space)


def factor_next(ts, at):
    t = ts[at]
    return t.kind == 'identifier' and t.symbol == 'none' or t.kind in NUMBERS


def juxtaposed(ts, at, after_group):
    """`2x`, `2(x+1)` (not `2()`, a call), `(5)x`, `(x)2`"""
    t = ts[at]
    group = t.symbol == 'lparen'
    if (t.kind == 'identifier' or group and ts[at + 1].symbol != 'rparen') and coefficient_before(ts, at):
        return True
    return not group and after_group and factor_next(ts, at)


def excluded(ts, at):
    """`f(x)g(x)`, `xs[i]y`"""
    return at > 0 and factor_next(ts, at) and ts[at - 1].symbol in ('rparen', 'rbrack')


def excluded_message(ts, at):
    if ts[at - 1].symbol == 'rbrack':
        return 'an indexed element is not a coefficient: write `*` (`xs[i] * y`); whitespace separates expressions'
    return 'a call result is not a coefficient: write `*` (`f(x) * g(x)`); whitespace separates expressions'


def double_closes(ts, at):
    """`<<` opening two type-argument blocks: an unspaced `>>` closes them on this line"""
    i = at + 1
    if i >= len(ts) or ts[i].space:
        return False
    depth = 0
    while i < len(ts) and ts[i].kind != 'eof' and not ts[i].newline:
        s = ts[i].symbol
        if s in ('lparen', 'lbrack', 'lbrace'):
            depth += 1
        elif s in ('rparen', 'rbrack', 'rbrace'):
            depth -= 1
            if depth < 0:
                return False
        elif s == 'shr' and depth == 0 and not ts[i].space:
            return True
        i += 1
    return False


def habit(ts, at, text):
    before = ts[at - 2].symbol if at >= 2 else 'none'
    adjacent = at >= 2 and not ts[at - 1].space
    pairs = {'*': ('star', ' (`^` raises to a power: `x^2`)'), '&': ('amp', ' (`and` joins conditions: `a and b`)'),
             '|': ('pipe', ' (`or` joins conditions: `a or b`)')}
    if text in pairs and before == pairs[text][0] and adjacent:
        return pairs[text][1]
    if text == '!':
        return ' (`not x` negates, and `x not=? y` asks whether two values differ)'
    if text == '=' and before in ('assign', 'eq') and adjacent:
        return ' (`=?` compares: `x =? y`; `=` gives a value)'
    if text in ('>', '<', '>=', '<='):
        return ' (comparisons end with `?`: `x >? y`, `x <=? y`)'
    for sign, words in (('plus', 'adds one'), ('minus', 'takes one away')):
        if before == sign and at >= 3 and ts[at - 3].symbol == sign:
            return f' (`x {"+" if sign == "plus" else "-"}= 1` {words})'
    return ''


def spec_ok(spec: bytes):
    """[[fill]align][+][#][0][width][,|_][.precision][type], the fill one byte"""
    i, n = 0, len(spec)
    if n >= 2 and spec[1:2] in (b'<', b'>', b'^'):
        i = 2
    elif n >= 1 and spec[0:1] in (b'<', b'>', b'^'):
        i = 1
    for mark in (b'+', b'#'):
        if spec[i:i + 1] == mark:
            i += 1
    while spec[i:i + 1].isdigit():
        i += 1
    if spec[i:i + 1] in (b',', b'_'):
        i += 1
    if spec[i:i + 1] == b'.':
        i += 1
        if not spec[i:i + 1].isdigit():
            return False
        while spec[i:i + 1].isdigit():
            i += 1
    if i < n and spec[i:i + 1] in [bytes([c]) for c in b'feEgG%xXbods']:
        i += 1
    return i == n


def spec_colon(source: bytes, start, stop):
    """the last colon outside brackets and quotes, not first or last, whose rest is a spec"""
    depth, found, i = 0, -1, start
    while i < stop:
        c = source[i:i + 1]
        if c in (b'"', b"'"):
            end = source.find(c, i + 1, stop)
            if end < 0:
                return -1
            i = end + 1
            continue
        if c in (b'(', b'[', b'{'):
            depth += 1
        elif c in (b')', b']', b'}'):
            depth -= 1
        elif c == b':' and depth == 0 and start < i < stop - 1:
            found = i
        i += 1
    return found if found >= 0 and spec_ok(source[found + 1:stop]) else -1


def lexemes(r):
    out = []
    for _ in range(r.randint(1, 12)):
        roll = r.random()
        if roll < 0.25:
            lexeme = Lexeme('identifier', r.choice(['none'] * 6 + ['kw_if', 'kw_and', 'kw_let', 'kw_not', 'kw_test']))
        elif roll < 0.45:
            lexeme = Lexeme(r.choice(sorted(NUMBERS)))
        elif roll < 0.55:
            lexeme = Lexeme(r.choice(['quoted', 'rawquoted', 'metatag', 'boolean', 'based_string']))
        elif roll < 0.8:
            lexeme = Lexeme('op', r.choice(['lparen', 'rparen', 'lbrack', 'rbrack', 'dot', 'shl', 'shr', 'star',
                                            'amp', 'pipe', 'assign', 'eq', 'plus', 'minus', 'plus', 'minus', 'range', 'comma']))
        else:
            lexeme = Lexeme('op', r.choice(TOKENS[1:]))
        lexeme.space = r.random() < 0.35
        lexeme.newline = r.random() < 0.1
        out.append(lexeme)
    out.append(Lexeme('eof', space=r.random() < 0.5))
    return out


SPECS = [b'.2f', b'>8,', b'^10', b'*<5', b'+#08.3e', b'_', b'x', b'%', b'\x80>4', b'\xc3\xa9>3', b'5d', b'08_.1%',
         b'.f', b'zz', b'\x80\x81', b'.', b'>8.2fx', b'', b'::', b' 4']
VALUES = [b'x', b'f(a, b)', b'[1 2]', b'{y}', b'"a:b"', b"'c:d'", b'"open', b':', b')', b'(', b'm[k:v]']


def spec_source(r):
    """an interpolation's text: values, then often a colon and a spec (some malformed)"""
    parts = [r.choice(VALUES) for _ in range(r.randint(0, 3))]
    if r.random() < 0.8:
        parts += [b':', r.choice(SPECS)]
    source = b''.join(parts)
    # (the text ends at its interpolation's closing brace, or where the source does)
    stop = len(source)
    if r.random() < 0.5:
        source += b'}' + r.choice(VALUES)
    return source, r.randint(0, 1), stop


def corpus(seed=14):
    r = random.Random(seed)
    lines, want = [], []
    for t in TOKENS:
        lines.append(f'O\t{TOKENS.index(t)}')
    for name in METATAGS:
        lines.append(f'D\t{name}')
        want.append(f'{FORMS.get(name, 0)} {int(name in DESIGNED)}')
    for _ in range(400):
        ts = lexemes(r)
        lines.append('T\t' + ' '.join(f'{KINDS.index(x.kind)},{TOKENS.index(x.symbol)},{int(x.space)},{int(x.newline)}'
                                      for x in ts))
        for at in range(len(ts)):
            group = r.random() < 0.5
            lines.append(f'Q\t{at}\t{int(group)}')
            got = [can_start(ts, at), range_bound(ts, at), coefficient_before(ts, at), factor_next(ts, at),
                   double_closes(ts, at)]
            if at + 1 < len(ts):
                got.append(juxtaposed(ts, at, group))
            got.append(excluded(ts, at))
            answer = ' '.join(str(int(g)) for g in got)
            want.append(answer + (' ' + excluded_message(ts, at) if excluded(ts, at) else ''))
            text = r.choice(HABIT_TEXTS)
            lines.append(f'H\t{at}\t{text}')
            want.append(f'[{habit(ts, at, text)}]')
    for _ in range(3000):
        source, start, stop = spec_source(r)
        if stop < start:
            continue
        lines.append(f'S\t{source.hex()}\t{start}\t{stop}')
        want.append(str(spec_colon(source, start, stop)))
    return '\n'.join(lines) + '\n', want


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def check_operators(rows):
    """each token's `power right prefix prefix-as-effect-no chain partial` against the table"""
    power, right, prefix, effect, chain, partial = {}, {}, {}, {}, {}, {}
    for t, row in zip(TOKENS, rows):
        p, rt, pre, eff, ch, pa = row.split()
        power[t], right[t], prefix[t], effect[t], chain[t], partial[t] = int(p), rt == '1', int(pre), int(eff), int(ch), pa == '1'
    for t in TOKENS:
        assert (power[t] > 0) == ranked(t), t
        assert right[t] == (ROW.get(t, (0, ''))[1] == 'right'), t
        assert chain[t] == CHAIN.get(t, 2), t
        assert partial[t] == (t in PARTIAL), t
    infix = [t for t in TOKENS if ranked(t)]
    for a in infix:
        for b in infix:
            # (a tighter row binds more tightly; one row, one power)
            assert (ROW[a][0] < ROW[b][0]) == (power[a] > power[b]), (a, b)
    # (a prefix operator's operand takes exactly the operators of the rows above its own)
    for t, name in [*PREFIXES.items(), ('no', 'no')]:
        level = effect['kw_not'] if t == 'no' else prefix[t]
        for x in infix:
            assert (power[x] >= level) == (ROW[x][0] < ROW[name][0]), (t, x)


def test_corpus_reaches_every_answer():
    _, want = corpus()
    joined = '\n'.join(want)
    for text in ['indexed element', 'call result', 'raises to a power', 'joins conditions', 'compares:', 'end with',
                 'adds one', 'takes one away', 'negates']:
        assert text in joined, text
    flags = [w.split()[:5] for w in want if w[:2] in ('0 ', '1 ') and len(w.split()) >= 6]
    for column in range(5):
        assert {f[column] for f in flags} == {'0', '1'}, column
    # (the juxtaposition column, where there is one)
    assert {w.split()[5] for w in want if w[:2] in ('0 ', '1 ') and len(w.split()) == 7} == {'0', '1'}
    colons = [w for w in want if w.lstrip('-').isdigit()]
    assert sum(w != '-1' for w in colons) > 300 and sum(w == '-1' for w in colons) > 300


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_grammar_match_jo(compiler, tmp_path, release):
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/dewy_grammar.jo'"
    assert twin in driver
    text, want = corpus()
    questions = tmp_path / 'questions'
    questions.write_text(text)
    outputs = []
    for module in ('dewy_grammar.dewy', 'dewy_grammar.jo'):
        source = tmp_path / f'driver-{module.replace(".", "-")}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'").replace("use '../../../", f"use '{ROOT}/"))
        binary = build(compiler, source, tmp_path / source.stem, release)
        ran = subprocess.run([binary, questions], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    got = outputs[0].split('\n')
    check_operators(got[:len(TOKENS)])
    for line, (answer, expected) in enumerate(zip(got[len(TOKENS):], want)):
        assert answer == expected, (line, text.split('\n')[len(TOKENS) + line])
    assert len(got) == len(TOKENS) + len(want) + 1


@pytest.mark.core_quick
def test_selfhost_dewy_grammar_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_grammar.dewy\0' in binary
    assert b'/compiler/dewy_grammar.jo\0' not in binary
    main = tmp_path / 'main.dewy'
    main.write_text("main=():>void=>{\n"
                    "    let x=3\n"
                    "    let s=[1.5 2.5]\n"
                    "    printl(2x^2 + (x)2 - -x^2)\n"
                    "    printl(not x =? 2 and 0 <? x <=? 3)\n"
                    "    printl('{x:>4}|{s[1]:.2f}|{['a:b' 'c'][0]}')\n"
                    "    printl([1 2 3].map((* 2)))\n"
                    "}\n")
    ran = subprocess.run([compiler, 'run', main], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0 and ran.stdout == '33\ntrue\n   3|2.50|a:b\n[2 4 6]\n', ran.stdout + ran.stderr
    main.write_text("main=():>void=>{\n    let f=(x:int64):>int64=>x\n    printl(f(2)f(3))\n}\n")
    checked = subprocess.run([compiler, 'check', main], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0
    assert 'a call result is not a coefficient' in checked.stdout + checked.stderr
