"""compiler/literals.dewy, a Dewy literal's text to its value (whole numbers in any base,
based strings packed into bytes, a string's escapes, what is wrong with a format spec): it ships, and its frozen
implementation-language twin compiler/literals.jo gives the same answers. The oracle is the
rules below, on bytes: a based number's text is its prefix (`0x:`) and digits, letters in
either case, `_` skipped, the prefix possibly written again; one past 64 bits has no word
value; a based string packs its digits' bits most significant first, base 64 (`0g:`, digits
then lowercase, uppercase, `+/`) as written and also taking `-` `_` and `=` padding; a
string escape is a letter (n r t 0 a b v f), a line break, `u` with four hexadecimal digits
or one to six in braces naming a scalar, or ASCII punctuation for itself; a format spec
is [[fill]align][+][#][0][width][,][.precision][type]."""
import re
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'

BASES = {b'0b:': b'01', b'0t:': b'012', b'0q:': b'0123', b'0s:': b'012345', b'0o:': b'01234567',
         b'0d:': b'0123456789', b'0z:': b'0123456789xe', b'0x:': b'0123456789abcdef'}
B64 = b'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/'
PACKINGS = {b'0b:': (b'01', 1), b'0q:': (b'0123', 2), b'0o:': (b'01234567', 3), b'0x:': (b'0123456789abcdef', 4),
            b'0u:': (b'0123456789abcdefghijklmnopqrstuv', 5), b'0g:': (B64, 6)}
LETTERS = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('0'): 0, ord('a'): 7, ord('b'): 8, ord('v'): 11, ord('f'): 12}
UNKNOWN = (b': the letter escapes are \\n \\r \\t \\a \\b \\v \\f, \\0 and \\u{...}, and any ASCII punctuation '
           b'escapes to itself')


class Problem(Exception):
    def __init__(self, message, at=0, unsupported=False):
        super().__init__(message)
        self.text = b'! %s @%d %s' % (message if isinstance(message, bytes) else message.encode(), at,
                                      b'true' if unsupported else b'false')


def lower(c):
    return c + 32 if 65 <= c <= 90 else c


def digits(text):
    if not (len(text) >= 3 and text[2:3] == b':'):
        return b'0123456789', 0
    if text[:3] not in BASES:
        raise Problem('this numeric base', 0, True)
    first = 5 if len(text) >= 5 and text[3:4] == b'0' and lower(text[4]) == text[1] else 3
    return BASES[text[:3]], first


def value(text):
    alphabet, first = digits(text)
    n = 0
    for i in range(first, len(text)):
        if text[i] == ord('_'):
            continue
        d = alphabet.find(bytes([lower(text[i])]))
        if d < 0:
            raise Problem('invalid numeric digit', i)
        if n > (2 ** 64 - 1 - d) // len(alphabet):
            return None
        n = n * len(alphabet) + d
    return n


def limbs(text):
    alphabet, first = digits(text)
    n = 0
    for i in range(first, len(text)):
        if text[i] == ord('_'):
            continue
        d = alphabet.find(bytes([lower(text[i])]))
        if d < 0:
            raise Problem('invalid numeric digit', i)
        n = n * len(alphabet) + d
    out = []
    while n:
        out.append(n & 0xFFFFFFFF)
        n >>= 32
    return out


def packed(text):
    if text[:3] not in PACKINGS or len(text) < 3:
        raise Problem('this based-string packing', 0, True)
    alphabet, width = PACKINGS[text[:3]]
    bits = []
    padded = False
    for i in range(3, len(text)):
        c = text[i]
        if width != 6 and c == ord('_'):
            continue
        if width == 6 and c == ord('='):
            padded = True
            continue
        if padded:
            raise Problem('based-string padding must be at the end', i)
        if width == 6:
            d = {ord('-'): 62, ord('_'): 63}.get(c, alphabet.find(bytes([c])))
        else:
            d = alphabet.find(bytes([lower(c)]))
        if d < 0:
            raise Problem('invalid based-string digit', i)
        bits += [(d >> k) & 1 for k in range(width - 1, -1, -1)]
    bits += [0] * (-len(bits) % 8)
    return bytes(int(''.join(map(str, bits[k:k + 8])), 2) for k in range(0, len(bits), 8))


def scalar(s, i, stop):
    at = i + 1
    braced = at < stop and s[at] == ord('{')
    if braced:
        at += 1
    first = at
    v = 0
    while at < stop:
        if braced and s[at] == ord('}'):
            break
        if not braced and at - first == 4:
            break
        d = int(chr(s[at]), 16) if chr(s[at]) in '0123456789abcdefABCDEF' else -1
        if d < 0:
            raise Problem('expected hexadecimal digits in Unicode escape', at)
        if at - first >= 6:
            raise Problem('Unicode escape has too many digits', i)
        v = v * 16 + d
        at += 1
    if braced:
        if at == first or at >= stop or s[at] != ord('}'):
            raise Problem("expected 1–6 hex digits and '}' in Unicode escape", i)
        at += 1
    elif at - first != 4:
        raise Problem('Unicode escape needs four hex digits', i)
    if v > 0x10FFFF or 0xD800 <= v <= 0xDFFF:
        raise Problem('Unicode escape must name a scalar value, not a surrogate or out-of-range code point', i)
    return chr(v).encode(), at


def escape(out, s, i, stop):
    at = i + 1
    if at >= stop:
        raise Problem('incomplete string escape', at)
    c = s[at]
    if c in (ord('u'), ord('U')):
        b, after = scalar(s, at, stop)
        out += b
        return after
    if c in LETTERS:
        out.append(LETTERS[c])
    elif c == 10:
        pass
    elif c == 13 and at + 1 < stop and s[at + 1] == 10:
        return at + 2
    elif 32 < c < 127 and not chr(c).isalnum():
        out.append(c)
    elif 0x80 <= c < 0xC0:
        raise Problem(b'unknown escape `\\` before the byte %d' % c + UNKNOWN, at)
    else:
        j = at + 1
        while j < len(s) and 0x80 <= s[j] < 0xC0:
            j += 1
        raise Problem(b'unknown escape `\\' + s[at:j] + b'`' + UNKNOWN, at)
    return at + 1


def char_at(s, i):
    if 0x80 <= s[i] < 0xC0:
        return b'byte %d' % s[i]
    j = i + 1
    while j < len(s) and 0x80 <= s[j] < 0xC0:
        j += 1
    return s[i:j]


def spec_problem(spec):
    # (the fill is any one byte before an alignment; an alignment alone needs no fill)
    i = 2 if len(spec) >= 2 and spec[1:2] in (b'<', b'>', b'^') else 1 if spec[:1] in (b'<', b'>', b'^') else 0
    m = re.compile(rb'\+?#?[0-9]*[,_]?').match(spec, i)
    i = m.end()
    if spec[i:i + 1] == b'.':
        m = re.compile(rb'[0-9]+').match(spec, i + 1)
        if not m:
            return b"a '.' needs the number of decimals after it"
        i = m.end()
    if i < len(spec):
        if spec[i] not in b'feEgG%xXbods':
            return b"'%s' is not a format type" % char_at(spec, i)
        i += 1
    if i < len(spec):
        while i < len(spec) and 0x80 <= spec[i] < 0xC0:
            i += 1
        return b"'%s' after the format is not part of one" % spec[i:]
    return b''


def listed(xs):
    return b','.join(b'%d' % x for x in xs)


def expected(words):
    out = []
    for w in words:
        kind, text = w[:1], w[1:]
        if kind == b'n':
            try:
                v = value(text)
                shown = b'big' if v is None else b'%d' % v
            except Problem as p:
                shown = p.text
            try:
                more = listed(limbs(text))
            except Problem as p:
                more = p.text
            out.append(shown + b' | ' + more)
        elif kind == b'f':
            out.append(spec_problem(text) or b'ok')
        elif kind == b's':
            try:
                out.append(listed(packed(text)))
            except Problem as p:
                out.append(p.text)
        else:
            got = bytearray()
            i = 0
            try:
                while i < len(text):
                    if text[i] == ord('\\'):
                        i = escape(got, text, i, len(text))
                    else:
                        got.append(text[i])
                        i += 1
                out.append(listed(got))
            except Problem as p:
                out.append(p.text + b' ' + listed(got))
    return b'\n'.join(out) + b'\n'


FIXED = [b'n', b'n0', b'n123', b'n1_000', b'n18446744073709551615', b'n18446744073709551616', b'n99999999999999999999',
         b'n0x:', b'n0x:ff', b'n0x:FF_ff', b'n0x:0xFF', b'n0x:0XfF', b'n0b:0b101', b'n0z:XE1', b'n0t:2102', b'n0s:55',
         b'n0o:777', b'n0d:42', b'n0x:fg', b'n0b:102', b'n0u:12', b'n0g:12', b'n0', b'n0x', b'n12a', b'n1:2',
         b'n0x:ffffffffffffffff', b'n0x:1_0000_0000_0000_0000', b'n0b:' + b'1' * 64, b'n0b:' + b'1' * 65 + b'2',
         b's0g:QUJD', b's0g:QQ==', b's0g:Q=Q', b's0g:-_+/', b's0x:4142', b's0x:4_1', b's0X:41', b's0u:vv', b's0b:1',
         b's0q:3', b's0o:7', b's0x:', b's0t:1', b's0x:4g', b's0', b's',
         b'e', b'eplain', b'eab\\ncd', b'e\\r\\t\\0\\a\\b\\v\\f', b'e\\u00e9', b'e\\U00E9', b'e\\u{1F600}x', b'e\\u{10FFFF}',
         b'e\\u{110000}', b'e\\u{D800}', b'e\\uD7FF', b'e\\u{}', b'e\\u{1234567}', b'e\\u{12', b'e\\u12', b'e\\u12g4',
         b'e\\q', b'e\\1', b'e\\ ', b'e\\\t', b'e\\\n', b'e\\\r\n', b'e\\\rx', b'e\\', b'ea\\', b'e\\{\\}\\"\\\'\\\\',
         b'f', b'f>8', b'f<', b'f*^10.3f', b'f.2', b'f.', b'f.x', b'f+#08,.2%', b'f_d', b'fq', b'f2fx', 'f\u00e9>8'.encode(),
         'f\u00e9'.encode(), b'f\x80', b'fd\x80\x80a', b'f<<', b'f>>8', b'f,', b'f8,_',
         'e\\é'.encode(), 'e\\😀x'.encode(), b'e\\\x80', b'e\\\xc3', b'e\\\xc3\xa9\xa9\xa9\xa9', b'e\\\x01', b'e\\\x7f']


def numbers(rng):
    prefix = rng.choice(list(BASES) + [b'', b'', b'', b'0u:', b'0X:', b'1x:'])
    chars = BASES.get(prefix, b'0123456789')
    chars += chars.upper() + b'_'
    if rng.random() < 0.15:
        prefix += prefix[:2] if rng.random() < 0.5 else prefix[:2].upper()
    text = bytearray(rng.choice(chars) for _ in range(rng.choice([1, 3, 12, 20, 30, 70])))
    if rng.random() < 0.1:
        text.insert(rng.randrange(len(text) + 1), rng.choice(b'gz!:\xc3\x80'))
    return b'n' + prefix + bytes(text)


def strings(rng):
    prefix = rng.choice(list(PACKINGS) * 3 + [b'0t:', b'0z:', b'0G:'])
    alphabet, width = PACKINGS.get(prefix, (b'01', 1))
    chars = alphabet + b'-_' if width == 6 else alphabet + alphabet.upper() + b'_'
    text = bytes(rng.choice(chars) for _ in range(rng.randrange(0, 24)))
    if width == 6 and rng.random() < 0.3:
        text += b'=' * rng.randrange(1, 3)
    if rng.random() < 0.1:
        k = rng.randrange(len(text) + 1)
        text = text[:k] + bytes([rng.choice(b'!= \xc3')]) + text[k:]
    return b's' + prefix + text


GOOD = [b'a', b'x', b' ', '\u00e9'.encode(), '\U0001F600'.encode(), b'\n', b'{', b'\\n', b'\\t', b'\\r', b'\\0',
        b'\\a', b'\\b', b'\\v', b'\\f', b'\\\\', b'\\"', b'\\{', b'\\}', b'\\#', b'\\u0041', b'\\U00e9',
        b'\\u{41}', b'\\u{1F600}', b'\\u{0}', b'\\u{10FFFF}', b'\\\n', b'\\\r\n', b'\xc3']
BAD = [b'\\u{D83D}', b'\\u{FFFFFF}', b'\\u{1234567}', b'\\u004', b'\\u{', b'\\u{}', b'\\uZZZZ', b'\\x41',
       b'\\q', b'\\9', b'\\\r', b'\\ ', '\\\u00e9'.encode(), b'\\\xbf', b'\\\x01']


def escapes(rng):
    text = b''.join(rng.choice(GOOD) for _ in range(rng.randrange(0, 8)))
    if rng.random() < 0.25:
        text += rng.choice(BAD) + b''.join(rng.choice(GOOD) for _ in range(rng.randrange(0, 3)))
    elif rng.random() < 0.05:
        text += b'\\'
    return b'e' + text


def specs(rng):
    parts = [rng.choice([b'', b'', b'*', b'0', '\u00e9'.encode(), b' ']) + rng.choice([b'<', b'>', b'^']) if rng.random() < 0.4 else b'',
             rng.choice([b'', b'+']), rng.choice([b'', b'#']), rng.choice([b'', b'0', b'08', b'12']), rng.choice([b'', b',', b'_']),
             rng.choice([b'', b'', b'.2', b'.', b'.x', b'.10']), rng.choice([b'', b'f', b'x', b'd', b'%', b's', b'q', b'\xc3\xa9', b'\x80'])]
    if rng.random() < 0.15:
        parts.append(rng.choice([b'x', b'zz', b'\x80a', '\u00e9'.encode(), b'2f']))
    return b'f' + b''.join(parts)


def words():
    rng = random.Random(20261024)
    out = list(FIXED)
    for _ in range(300):
        out.append(rng.choice([numbers, numbers, strings, escapes, escapes, specs])(rng))
    return out


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(binary, args):
    ran = subprocess.run([binary, *args], capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_literals_match_jo(compiler, tmp_path, release):
    args = words()
    dewy = build(compiler, FIXTURES / 'literals_dewy.dewy', tmp_path / 'literals-dewy', release)
    jo = build(compiler, FIXTURES / 'literals_jo.jo', tmp_path / 'literals-jo', release)
    got = run(dewy, args)
    assert got == run(jo, args)
    assert got == expected(args)


@pytest.mark.core_quick
def test_selfhost_literals_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/literals.dewy\0' in binary
    assert b'/compiler/literals.jo\0' not in binary
