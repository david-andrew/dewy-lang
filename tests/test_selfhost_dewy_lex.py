"""compiler/dewy_lex.dewy (the Dewy lexer's scanners: a quoted string's end, an interpolation's
closing brace, a block comment's end, a skipped library body's end, and the state they keep)
ships, and its frozen implementation-language twin compiler/dewy_lex.jo gives the same answers.
Two drivers call either module at every quote, brace and `#` of the repository's Dewy files and
of generated texts (nested and unterminated strings, interpolations, comments, raw and triple
quotes); a Python oracle written from the lexer's rules gives the expected lines."""
import random
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'

HINT = '`{...}` in a string holds an expression: write `\\{` and `\\}` for literal braces, or use a raw string `r"..."`'
OPEN = f'unterminated string: this `{{` starts a string interpolation that does not end ({HINT})'
BLOCK = 'unterminated block comment: `#{` needs a matching `}#` (block comments nest)'


def ident_start(c):
    return 97 <= c <= 122 or 65 <= c <= 90 or c == 95 or c >= 128


def ident_part(c):
    return ident_start(c) or 48 <= c <= 57


def decimal(c):
    return 48 <= c <= 57 or c == 95


class Scanner:
    """The scanners and their state, as dewy_lex.dewy keeps them."""

    def __init__(self, s):
        self.s = s
        self.suspect = -1
        self.open = -1
        self.problem = None     # (at, note, message)

    def fail(self, at, message):
        self.problem = (at, -1, message)
        return -1

    def unterminated(self, start, message):
        suspect, open_ = self.suspect, self.open
        if 0 <= open_ < start:
            self.fail(open_, OPEN)
        else:
            self.fail(start, message)
        if 0 <= suspect < start and suspect != open_:
            self.problem = (self.problem[0], suspect, self.problem[2])
        return -1

    def width(self, start, stop):
        s = self.s
        return 3 if start + 2 < stop and s[start + 1] == s[start] and s[start + 2] == s[start] else 1

    def block_end(self, i, stop):
        s = self.s
        i += 2
        depth = 1
        while i + 1 < stop:
            if s[i] == 35 and s[i + 1] == 123:
                depth += 1
                i += 2
            elif s[i] == 125 and s[i + 1] == 35:
                depth -= 1
                i += 2
                if depth == 0:
                    return i
            else:
                i += 1
        return -1

    def interpolation_end(self, start, stop, nesting, incomplete):
        s = self.s
        i, depth, parens, spec = start, 1, 0, False
        while i < stop:
            c = s[i]
            if c == 35 and spec:
                i += 1
                continue
            if c == 58 and depth == 1 and parens == 0:
                spec = True
            elif c in (32, 9, 10):
                spec = False
            elif c in (40, 91):
                parens += 1
            elif c in (41, 93):
                parens -= 1
            if c == 35 and i + 1 < stop and s[i + 1] == 123:
                e = self.block_end(i, stop)
                if e < 0:
                    return -1 if incomplete else self.fail(i, BLOCK)
                i = e
                continue
            if c == 35:
                while i < stop and s[i] != 10:
                    i += 1
                continue
            if c == 114 and i + 1 < stop and s[i + 1] in (34, 39) and (i == start or not ident_part(s[i - 1])):
                i = self.quote_end(i + 1, stop, nesting, True, incomplete)
                if i < 0:
                    return -1
                continue
            if c in (34, 39):
                i = self.quote_end(i, stop, nesting, False, incomplete)
                if i < 0:
                    return -1
                continue
            if c == 123:
                depth += 1
            elif c == 125:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return -1 if incomplete else self.unterminated(start, 'unterminated string interpolation')

    def quote_end(self, start, stop, nesting, raw, incomplete):
        s = self.s
        if start >= stop:
            return -1 if incomplete else self.unterminated(start, 'unterminated string')
        if nesting >= 256:
            return -1 if incomplete else self.fail(start, 'string interpolation is nested too deeply')
        q = s[start]
        width = self.width(start, stop)
        i = start + width
        first = -1
        if nesting == 0:
            self.open = -1
        while i < stop:
            c = s[i]
            if not raw and c == 92:
                i += 2
                continue
            if c == q:
                if width == 1:
                    return i + 1
                if i + 2 < stop and s[i + 1] == q and s[i + 2] == q:
                    return i + 3
            if not raw and c == 123:
                if first < 0:
                    first = i
                if nesting == 0:
                    self.open = first
                if self.suspect < 0 and i + 1 < stop and s[i + 1] == q:
                    self.suspect = i
                e = self.interpolation_end(i + 1, stop, nesting + 1, incomplete)
                if e < 0:
                    return -1
                i = e + 1
                continue
            i += 1
        if incomplete:
            return -1
        if nesting == 0 and first >= 0:
            return self.unterminated(first + 1, 'unterminated string')
        return self.unterminated(start, 'unterminated string')

    def lazy_end(self, i0, stop):
        """A skipped body's end: -1 where it holds what parsing must see at once."""
        s = self.s
        if i0 < 0 or i0 >= stop:
            return -1
        i, depth = i0 + 1, 1
        while True:
            while i < stop and not (ident_part(s[i]) or s[i] in b'{}#"\'$=?'):
                i += 1
            if i >= stop:
                return -1
            c = s[i]
            if ident_start(c):
                j = i + 1
                while j < stop and ident_part(s[j]):
                    j += 1
                if s[i:j] in (b'import', b'from'):
                    return -1
                i = j
            elif 48 <= c <= 57:
                if c == 48 and i + 1 < stop and s[i + 1] in b'btqsodzxug':
                    return -1
                j = i
                while j < stop and decimal(s[j]):
                    j += 1
                if j - i > 18:
                    return -1
                while j < stop and ident_part(s[j]):
                    j += 1
                i = j
            elif c == 123:
                depth += 1
                i += 1
            elif c == 125:
                depth -= 1
                i += 1
                if depth == 0:
                    return i
            elif c == 35:
                if i + 1 < stop and s[i + 1] == 123:
                    e = self.block_end(i, stop)
                    if e < 0:
                        return -1
                    i = e
                else:
                    while i < stop and s[i] != 10:
                        i += 1
            elif c in (34, 39):
                raw = i > 0 and s[i - 1] == 114 and (i < 2 or not ident_part(s[i - 2]))
                width = self.width(i, stop)
                i += width
                while True:
                    if i >= stop:
                        return -1
                    d = s[i]
                    if d in (123, 125):
                        return -1
                    if d == 92 and not raw:
                        i += 2
                        continue
                    if d == c and (width == 1 or i + 2 < stop and s[i + 1] == c and s[i + 2] == c):
                        i += width
                        break
                    i += 1
            elif c == 36:
                return -1
            elif c == 61:
                if i + 1 < stop and s[i + 1] == 62:
                    return -1
                i += 1
            else:
                if i + 1 < stop and s[i + 1] == 63:
                    return -1
                i += 1


def oracle(src):
    """The drivers' lines for one text (tests/fixtures/selfhost/dewy_lex_dewy.dewy)."""
    sc = Scanner(src)
    n = len(src)
    out = []

    def problem():
        at, note, message = sc.problem
        out.append(f'! {at} {note} {message}')

    for i in range(n):
        c = src[i]
        if c in (34, 39):
            raw = i > 0 and src[i - 1] == 114
            e = sc.quote_end(i, n, 0, raw, False)
            parts = [e, sc.width(i, n), sc.quote_end(i, n, 0, raw, True), sc.quote_end(i, n, 1, False, True)]
            out.append(f'q {i} ' + ' '.join(map(str, parts)))
            if e < 0:
                problem()
        if c == 123:
            e = sc.interpolation_end(i + 1, n, 0, False)
            out.append(f'b {i} {e} {sc.interpolation_end(i + 1, n, 2, True)} {sc.lazy_end(i, n)}')
            if e < 0:
                problem()
        if c == 35:
            out.append(f'c {i} {sc.block_end(i, n)}')
    out.append(f's {sc.suspect} {sc.open}')
    out.append('=')
    return out


def generated(rng, count):
    pieces = ['"', "'", '"""', "'''", 'r"', "r'", '{', '}', '{{', '#', '#{', '}#', '\\', '\\"', '\n', ' ',
              'x', 'r', ':', ':.2f', '(', ')', '[', ']', '$', '=>', '??', '0x', '123', 'import', 'from', 'é', 'a"{b}"',
              '"{x}"', '"a{"b"}c"', "'{'", '#{ "x" }#', 'f = (a) => {', 'let s="{', '"""\n{x}\n"""']
    texts = []
    for _ in range(count):
        texts.append(''.join(rng.choice(pieces) for _ in range(rng.randint(1, 40))))
    # (deep nesting: the limit is 256 interpolations)
    texts.append('"{' * 300 + '}"' * 300)
    texts.append('"{' * 200 + '}"' * 200)
    return texts


def corpus():
    files = [*sorted((ROOT / 'compiler').glob('*.dewy')), *sorted((ROOT / 'lib').rglob('*.dewy')),
             *sorted((ROOT / 'tests/ladder').rglob('*.dewy'))]
    texts = [p.read_text(encoding='utf-8') for p in files]
    return texts + generated(random.Random(11), 600)


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=180)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_lex_match_jo(compiler, tmp_path, release):
    sys.setrecursionlimit(20000)
    dewy = build(compiler, FIXTURES / 'dewy_lex_dewy.dewy', tmp_path / 'lex-dewy', release)
    jo = build(compiler, FIXTURES / 'dewy_lex_jo.jo', tmp_path / 'lex-jo', release)
    texts = corpus()
    cases = tmp_path / 'cases'
    cases.mkdir()
    paths = []
    for k, text in enumerate(texts):
        path = cases / f'{k}.dewy'
        path.write_text(text, encoding='utf-8')
        paths.append(str(path))
    listed = tmp_path / 'list'
    listed.write_text('\n'.join(paths) + '\n')
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, listed], capture_output=True, timeout=600)
        assert ran.returncode == 0, ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    got = (outputs[0].decode()).splitlines()
    want = [line for text in texts for line in oracle(text.encode())]
    assert len(got) == len(want)
    for k, (a, b) in enumerate(zip(got, want)):
        assert a == b, (k, a, b)
    # (the texts reach every outcome)
    assert sum(line.startswith('! ') for line in want) > 100
    assert any(line.startswith('! ') and line.split()[2] != '-1' for line in want)


def test_selfhost_dewy_lex_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_lex.dewy\0' in binary
    assert b'/compiler/dewy_lex.jo\0' not in binary
