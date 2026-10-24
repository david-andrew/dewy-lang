"""compiler/dewy_layout.dewy (the layout `dewy-core fmt` gives Dewy text) ships, and its frozen
implementation-language twin compiler/dewy_layout.jo lays out the same lexemes the same way.
The test lexes Dewy sources as the compiler's lexer does (dewy_fast.jo's dn_lex, without
interning), lays them out in Python, and checks both modules against that, on the repository's
Dewy files and on copies with their indentation, spacing and line ends disturbed. The compiler's
own `fmt` must agree with the oracle on a sample of them."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'


def token_table():
    """dewy_tokens.dewy's tokens in order, each with its spelling."""
    source = (ROOT / 'compiler/dewy_tokens.dewy').read_text()
    members = re.search(r"^DewyToken:type=(.*?)\n\n", source, re.M | re.S).group(1)
    order = re.findall(r"'([a-z_]+)'", members)
    body = re.search(r'dn_token_text=\(token:DewyToken\):>string=>match token \{\n(.*?)\n\}', source, re.S).group(1)
    text = {k: re.sub(r'\\(.)', r'\1', v) for k, v in re.findall(r"^    <'([a-z_]+)'> => \"((?:[^\"\\]|\\.)*)\"$", body, re.M)}
    return order, text


ORDER, TEXT = token_table()
SPELLED = {v: k for k, v in TEXT.items()}


def ident_start(c):
    return 97 <= c <= 122 or 65 <= c <= 90 or c == 95 or c >= 128


def ident_part(c):
    return ident_start(c) or 48 <= c <= 57


def digit(c):
    return 48 <= c <= 57


def pair_table():
    """dn_init_symbols: the token two bytes start (None: look further)."""
    singles = {}
    pairs = {}
    longer = set()
    last = ORDER.index('kw_or_throw')
    for name in ORDER[1:last + 1]:
        t = TEXT.get(name, '').encode()
        if len(t) == 1 and not ident_start(t[0]):
            singles[t[0]] = name
    for name in ORDER[1:last + 1]:
        t = TEXT.get(name, '').encode()
        if len(t) < 2 or ident_start(t[0]):
            continue
        slot = (t[0], t[1])
        if len(t) > 2:
            longer.add(slot)
            pairs[slot] = None
        elif slot not in longer:
            pairs[slot] = name
    return singles, pairs


SINGLES, PAIRS = pair_table()
# dn_lex_symbol: the longer spellings tried after each first byte, in order
LONGER = {'%': ['%='], '*': ['*='], '+': ['+='], '-': ['->', '-='],
          '.': ['.%=', '.%', '.*=', '.*', '.+=', '.+', '.-=', '.-', '...', '..', './/=', './=', './/', './', '.<=?',
                '.<?', '.=?', '.>=?', '.>?', '.^=', '.^', '.not>=?', '.not<=?', '.not=?', '.not>?', '.not<?'],
          '/': ['//=', '/=', '//'], ':': [':>'], '<': ['<=?', '<<=', '<?', '<<', '<|'], '=': ['=>', '=?'],
          '>': ['>=?', '>>=', '>?', '>>'], '?': ['??'], '^': ['^='], '|': ['|>', '|='], '&': ['&=']}


class LexError(Exception):
    pass


def block_end(s, i, stop):
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
    raise LexError('block comment')


def interpolation_end(s, start, stop, nesting):
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
            i = block_end(s, i, stop)
            continue
        if c == 35:
            while i < stop and s[i] != 10:
                i += 1
            continue
        if c == 114 and i + 1 < stop and s[i + 1] in (34, 39) and (i == start or not ident_part(s[i - 1])):
            i = quote_end(s, i + 1, stop, nesting, True)
            continue
        if c in (34, 39):
            i = quote_end(s, i, stop, nesting, False)
            continue
        if c == 123:
            depth += 1
        elif c == 125:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise LexError('interpolation')


def quote_end(s, start, stop, nesting=0, raw=False):
    if nesting >= 256:
        raise LexError('nesting')
    q = s[start]
    width = 3 if start + 2 < stop and s[start + 1] == q and s[start + 2] == q else 1
    i = start + width
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
            i = interpolation_end(s, i + 1, stop, nesting + 1) + 1
            continue
        i += 1
    raise LexError('string')


def op_symbol(s, at, stop):
    c = s[at]
    nxt = s[at + 1] if at + 1 < stop else 0
    if c < 128 and nxt < 128:
        name = PAIRS[(c, nxt)] if (c, nxt) in PAIRS else SINGLES.get(c)
        if name:
            return name
    for spelling in LONGER.get(chr(c), []):
        b = spelling.encode()
        if s[at:at + len(b)] == b:
            if spelling == '>>=' and s[at:at + 4] == b'>>=>':
                continue
            return SPELLED[spelling]
    name = SINGLES.get(c)
    if not name:
        raise LexError('character')
    return name


def lex(s):
    """dn_lex without interning: (kind, symbol, start, stop, space, newline) each, then eof, and
    the block comments' [start, end) pairs."""
    out, blocks = [], []
    n = len(s)
    i, spaced, newline = 0, False, False
    while i < n:
        c = s[i]
        if c in (32, 9, 13, 10):
            spaced = True
            newline = newline or c == 10
            i += 1
            continue
        if c == 92:
            e = i + 1
            while e < n and s[e] in (32, 9, 13):
                e += 1
            if e < n and s[e] == 10:
                spaced = True
                i = e + 1
                continue
        if c == 35 and i + 1 < n and s[i + 1] == 123:
            e = block_end(s, i, n)
            blocks += [i, e]
            newline = newline or 10 in s[i:e]
            spaced = True
            i = e
            continue
        if c == 35:
            while i < n and s[i] != 10:
                i += 1
            spaced = True
            continue
        start, kind, symbol = i, 'op', None
        if c == 114 and i + 1 < n and s[i + 1] in (34, 39):
            i = quote_end(s, i + 1, n, 0, True)
            kind = 'rawquoted'
        elif ident_start(c):
            if c >= 128:
                if out and out[-1][3] == start and out[-1][0] == 'identifier':
                    _, _, start, _, spaced, newline = out.pop()
                    i = start
                while i < n and ident_part(s[i]):
                    i += 1
            else:
                i += 1
                while i < n and ident_part(s[i]) and s[i] < 128:
                    i += 1
            kind = 'identifier'
            value = s[start:i]
            if value in (b'true', b'false'):
                kind = 'boolean'
            if value in (b'is', b'isnt', b'in') and i < n and s[i] == 63:
                value += b'?'
                i += 1
                kind = 'op'
            if kind != 'boolean':
                # (dn_token_kind: the keywords, and `is?`, `isnt?` and `in?`)
                symbol = SPELLED.get(value.decode(errors='replace'))
                if symbol and not (kind == 'op' or symbol.startswith('kw_')):
                    symbol = None
            if symbol in ('kw_and', 'kw_or', 'kw_xor') and i < n and s[i] == 61 and not (i + 1 < n and s[i + 1] in (63, 62, 61)):
                symbol = symbol[3:] + '_assign'
                kind = 'op'
                i += 1
        elif c == 36:
            i += 1
            while i < n and ident_part(s[i]) and s[i] < 128:
                i += 1
            if i == start + 1:
                raise LexError('metatag')
            kind = 'metatag'
        elif digit(c):
            decimal, digits = True, start
            if c == 48 and i + 1 < n and s[i + 1] in b'btqsodzxug':
                decimal = s[i + 1] == 100
                i += 2
                digits = i
            if i < n and s[i] in (34, 39):
                i = quote_end(s, i, n)
                kind = 'based_string'
            else:
                if decimal:
                    while i < n and (digit(s[i]) or s[i] == 95):
                        i += 1
                else:
                    while i < n and s[i] < 128 and (ident_part(s[i])):
                        i += 1
                if i == digits:
                    raise LexError('digits')
                kind = 'source_integer' if decimal else 'integer'
                if decimal and i + 1 < n and s[i] == 46 and digit(s[i + 1]):
                    i += 1
                    while i < n and (digit(s[i]) or s[i] == 95):
                        i += 1
                    kind = 'source_real'
                if decimal and i + 1 < n and s[i] in (101, 69) and (digit(s[i + 1]) or s[i + 1] in (43, 45)):
                    i += 1
                    if i < n and s[i] in (43, 45):
                        i += 1
                    first = i
                    while i < n and (digit(s[i]) or s[i] == 95):
                        i += 1
                    if i == first:
                        raise LexError('exponent')
                    kind = 'source_real'
        elif c in (34, 39):
            i = quote_end(s, i, n)
            kind = 'quoted'
        else:
            symbol = op_symbol(s, start, n)
            i += len(TEXT[symbol].encode())
        out.append((kind, symbol, start, i, spaced, newline))
        spaced = newline = False
    out.append(('eof', None, n, n, spaced, newline))
    return out, blocks


# ---- the layout, as the oracle sees it ----

ASSIGNMENTS = {'assign', 'function', 'returns'} | {k for k in TEXT if k.endswith('_assign')} - {'angle_assign'}
CLOSERS = {'rparen', 'rbrack', 'rbrace'}
OPENERS = {'lparen', 'lbrack', 'lbrace'}
WORD_OPS = {'amp', 'pipe', 'kw_and', 'kw_or', 'kw_xor'}


def assignment(sym):
    """`=`, `=>`, `:>` and the compound assignments (dn_token_assignment, read from its match)."""
    return sym in ASSIGNMENTS


def free_gap(a, b):
    return assignment(a) or assignment(b) or a in ('colon', 'comma', 'semi', 'lbrace') or b in ('colon', 'comma', 'rbrace')


class Layout:
    def __init__(self, src, tokens, blocks):
        self.src, self.tokens, self.blocks = src, tokens, blocks
        self.stack = []      # (opening, level)
        self.tracked = 0
        self.angles = 0

    def sym(self, i):
        return self.tokens[i][1]

    def function_value(self, at):
        toks, i = self.tokens, at + 1
        n = len(toks)
        for open_, close in (('langle', 'rangle'),):
            if i < n and toks[i][1] == open_:
                depth = 0
                while i < n:
                    depth += (toks[i][1] == open_) - (toks[i][1] == close)
                    i += 1
                    if depth == 0:
                        break
        if i >= n:
            return False
        if toks[i][0] == 'identifier':
            return i + 1 < n and toks[i + 1][1] == 'function'
        if toks[i][1] != 'lparen':
            return False
        depth = 0
        while i < n:
            depth += (toks[i][1] == 'lparen') - (toks[i][1] == 'rparen')
            i += 1
            if depth == 0:
                break
        return i < n and toks[i][1] in ('function', 'returns')

    def track(self, stop, level):
        while self.tracked < stop:
            kind, sym, _, _, space, _ = self.tokens[self.tracked]
            self.tracked += 1
            if kind != 'op':
                continue
            if sym == 'langle':
                self.angles += 1
            elif self.angles > 0 and (sym == 'rangle' or (sym == 'gt' and not space)):
                self.angles -= 1
            elif self.angles > 1 and sym == 'shr':
                self.angles -= 2
            if sym in OPENERS:
                self.stack.append((sym, level))
                if len(self.stack) > 256:
                    return False
            elif sym in CLOSERS:
                if not self.stack:
                    return False
                opening, _ = self.stack.pop()
                if (opening == 'lbrace') != (sym == 'rbrace'):
                    return False
        return True

    def gap(self, i):
        left, right = self.tokens[i - 1], self.tokens[i]
        a, b = left[1], right[1]
        if b in ('colon', 'comma') or a in ('colon', 'returns') or b == 'returns' or (a, b) == ('lbrace', 'rbrace'):
            return ''
        if self.angles > 0 and b in ('shr_assign', 'angle_assign'):
            return ''
        if a in ('shr_assign', 'angle_assign'):
            return ' '
        compound = ASSIGNMENTS - {'assign', 'returns'}
        if a in compound or b in compound:
            return ' '
        if 'assign' in (a, b):
            inside = self.angles > 0 or (self.stack and self.stack[-1][0] != 'lbrace')
            member = False
            if self.angles == 0 and self.stack and self.stack[-1][0] == 'lbrack':
                member = self.function_value(i) if b == 'assign' else self.function_value(i - 1)
            return ' ' if not inside or member or right[4] else ''
        if free_gap(a, b):
            return ' '
        return ' ' if right[4] else ''

    def run(self):
        s, toks = self.src, self.tokens
        crlf = b'\r\n' in s
        out = []
        at = opaque = bi = 0
        start = 0
        while start < len(s):
            end = s.find(b'\n', start)
            if end < 0:
                end = len(s)
            content_end = end - 1 if end > start and s[end - 1] == 13 else end
            newline = b'\r\n' if content_end < end else b'\n'
            if end == len(s):
                newline = b'\r\n' if crlf else b'\n'
            protected = start < opaque
            stop = at
            while toks[stop][0] != 'eof' and toks[stop][2] < content_end:
                if toks[stop][3] > content_end:
                    opaque = toks[stop][3]
                stop += 1
            while bi + 1 < len(self.blocks) and self.blocks[bi] < content_end:
                if self.blocks[bi + 1] > content_end:
                    opaque = max(opaque, self.blocks[bi + 1])
                bi += 2
            lead = 0
            while at + lead < stop and toks[at + lead][0] == 'op' and toks[at + lead][1] in CLOSERS:
                lead += 1
            depth = 0
            if self.stack:
                depth = self.stack[-1][1] + (0 if lead else 1)
            if not lead and 0 < at < stop and not protected:
                prev, first_sym = toks[at - 1][1], toks[at][1]
                if assignment(prev) or prev == 'comma' or prev in WORD_OPS or first_sym in WORD_OPS:
                    depth += 1
            line = s[start:content_end]
            body = line.lstrip(b' \t')
            first = content_end - len(body)
            last = content_end
            if not protected and opaque <= content_end:
                last = first + len(body.rstrip(b' \t'))
            if protected:
                out.append(line)
            elif first == content_end:
                pass
            else:
                parts = [b' ' * (4 * depth)]
                if at == stop:
                    parts.append(s[first:last])
                else:
                    parts.append(s[first:toks[at][2]])
                    for i in range(at, stop):
                        if i > at:
                            if not self.track(i, depth):
                                return None
                            between = s[toks[i - 1][3]:toks[i][2]]
                            parts.append(between if b'#' in between else self.gap(i).encode())
                        parts.append(s[toks[i][2]:min(toks[i][3], content_end)])
                    cursor = min(toks[stop - 1][3], content_end)
                    parts.append(s[cursor:last])
                out.append(b''.join(parts))
            if not self.track(stop, depth):
                return None
            self.angles = 0
            out.append(newline)
            at = stop
            start = end + 1
        if self.stack:
            return None
        return b''.join(out)


def disturbed(src, rng):
    """src with its indentation and the spaces between its tokens changed at random, and
    sometimes its line ends made CRLF (None when the text no longer lexes)."""
    try:
        tokens, _ = lex(src)
    except LexError:
        return None
    out = bytearray()
    at = 0
    for kind, _, start, stop, _, _ in tokens:
        between = src[at:start]
        if kind != 'eof' and at > 0 and b'#' not in between and b'\\' not in between:
            if b'\n' in between:
                k = between.rfind(b'\n')
                between = between[:k + 1].rstrip(b' \t') + b' ' * rng.choice([0, 0, 1, 3, 4, 8, 13])
                between = between.replace(b'\n', b' \n', 1) if rng.random() < 0.1 else between
            else:
                between = rng.choice([between, between, b'', b' ', b'  '])
        out += between + src[start:stop]
        at = stop
    out += src[at:]
    text = bytes(out)
    if rng.random() < 0.15:
        text = text.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    try:
        lex(text)
    except LexError:
        return None
    return text


def corpus():
    rng = random.Random(10)
    files = sorted(p for p in (ROOT / 'tests').rglob('*.dewy') if '__dewycache__' not in p.parts)
    files = [*sorted((ROOT / 'compiler').glob('*.dewy')), *sorted((ROOT / 'lib').rglob('*.dewy')),
             *sorted((ROOT / 'examples').glob('*.dewy')), *rng.sample(files, 500)]
    texts = []
    for path in files:
        src = path.read_bytes()
        try:
            src.decode()
            lex(src)
        except (UnicodeDecodeError, LexError):
            continue
        texts.append(src)
        for _ in range(2):
            if (d := disturbed(src, rng)) is not None:
                texts.append(d)
    texts += [b'', b'\n', b'f(\n', b')\n', b'x = [1\n  2}\n', b'#{ a\n b }# x=1\n  y=2\n', b'a = {\r\nb\r\n}',
              b'let s="a\n   b" c=(\n1\n)\n', b'x:array<array<int64>>=[]\n', b'  # alone  \n\t\n',
              b'm = [w = () => 1 v=2]\n', b'f(a=1 b = 2)\n', b'x = a\nand b\n', b'y=a +\nb\n',
              b'(' * 300 + b')' * 300 + b'\n', b'p = <T>(x:T) => x\n', b'q:>int64=x>=?1\n']
    return texts


def oracle(src):
    tokens, blocks = lex(src)
    return Layout(src, tokens, blocks).run()


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=180)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def write_cases(tmp_path, texts):
    rows = []
    for k, src in enumerate(texts):
        tokens, blocks = lex(src)
        lines = ['B ' + ' '.join(map(str, blocks))]
        for kind, sym, start, stop, space, newline in tokens:
            lines.append(f"{kind}\t{TEXT[sym] if sym else '-'}\t{start}\t{stop}\t{int(space)}\t{int(newline)}")
        (tmp_path / f'{k}.dewy').write_bytes(src)
        (tmp_path / f'{k}.lex').write_text('\n'.join(lines) + '\n')
        rows.append(f'{tmp_path}/{k}.dewy\t{tmp_path}/{k}.lex')
    listed = tmp_path / 'cases'
    listed.write_text('\n'.join(rows) + '\n')
    return listed


def results(output):
    out = []
    at = 0
    while at < len(output):
        end = output.index(b'\n', at)
        n = int(output[at + 4:end])
        if n < 0:
            out.append(None)
            at = end + 1
        else:
            out.append(output[end + 1:end + 1 + n])
            at = end + 1 + n + 1
    return out


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_layout_match_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'dewy_layout_dewy.dewy', tmp_path / 'layout-dewy', release)
    jo = build(compiler, FIXTURES / 'dewy_layout_jo.jo', tmp_path / 'layout-jo', release)
    texts = corpus()
    cases = tmp_path / 'cases'
    cases.mkdir()
    listed = write_cases(cases, texts)
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, listed], capture_output=True, timeout=300)
        assert ran.returncode == 0, ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    got = results(outputs[0])
    assert len(got) == len(texts)
    expected = [oracle(t) for t in texts]
    for k, (a, b) in enumerate(zip(got, expected)):
        assert a == b, (k, texts[k][:400])
    assert sum(g is None for g in got) >= 4
    assert sum(g is not None and g != t for g, t in zip(got, texts)) > len(texts) // 3


def test_selfhost_dewy_layout_fmt_agrees(compiler, tmp_path):
    # (the compiler's fmt lexes for itself: where it formats a file, it gives the oracle's text)
    rng = random.Random(3)
    texts = rng.sample([t for t in corpus() if t], 300)
    for k, src in enumerate(texts):
        (tmp_path / f'{k}.dewy').write_bytes(src)
    ran = subprocess.run([compiler, 'fmt', tmp_path], capture_output=True, timeout=300)
    refused = set(re.findall(rb'dewy-core fmt: (\S+?\.dewy):', ran.stderr))
    checked = 0
    for k, src in enumerate(texts):
        path = tmp_path / f'{k}.dewy'
        if str(path).encode() in refused:
            continue
        assert path.read_bytes() == oracle(src), (k, src[:400])
        checked += 1
    assert checked > 250


@pytest.mark.core_quick
def test_selfhost_dewy_layout_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_layout.dewy\0' in binary
    assert b'/compiler/dewy_layout.jo\0' not in binary
    ran = subprocess.run([compiler, 'fmt', '-'], input=b'f = (x:int64):>int64 => {\nlet y=[a=1 g = () => 2]\n  y}\n',
                         capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == b'f = (x:int64):>int64 => {\n    let y = [a=1 g = () => 2]\n    y }\n'
    # (text that is not UTF-8, as the compiler reads it unchecked, keeps its bytes)
    text = b'x = 1\n  # \x80 c\n  \x80abc=2\ns = "\x80\n\x80 "  \n'
    ran = subprocess.run([compiler, 'fmt', '-'], input=text, capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == oracle(text) == b'x = 1\n# \x80 c\n\x80abc = 2\ns = "\x80\n\x80 "  \n'
