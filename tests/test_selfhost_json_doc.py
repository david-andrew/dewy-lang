"""compiler/json_doc.dewy, the language server's JSON: it ships, and its frozen
implementation-language twin compiler/json_doc.jo gives the same answers. The oracle is
Python's json module (numbers kept as written, every member of an object kept) and the
rules below: a JSON string escapes quote, backslash, newline, tab and return by letter and
other control bytes as \\u00XX; half a surrogate pair reads as U+FFFD; a number's integer
part is the text before any '.', an optional sign and digits that fit in int64, else 0
(a boolean's is 0 or 1).
Malformed text has no oracle: the two must only agree."""
import json
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'


class Number(str):
    """A number as written."""


def quote(s):
    out = ['"']
    for ch in s:
        if ch in '"\\':
            out.append('\\' + ch)
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\r':
            out.append('\\r')
        elif ord(ch) < 32:
            out.append(f'\\u{ord(ch):04x}')
        else:
            out.append(ch)
    return ''.join(out + ['"'])


class Object(list):
    """An object's members in order, duplicates kept."""


def load(text):
    return clean(json.loads(text, parse_int=Number, parse_float=Number, parse_constant=Number,
                            object_pairs_hook=Object))


def clean(v):
    """Half a surrogate pair is U+FFFD."""
    if isinstance(v, Object):
        return Object((clean(k), clean(x)) for k, x in v)
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, str) and not isinstance(v, Number):
        return re.sub('[\ud800-\udfff]', '\ufffd', v)
    return v


def raw(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, Number):
        return str(v)
    if isinstance(v, str):
        return quote(v)
    if isinstance(v, Object):
        return '{' + ','.join(f'{quote(k)}:{raw(x)}' for k, x in v) + '}'
    return '[' + ','.join(raw(x) for x in v) + ']'


def integer(v):
    if isinstance(v, bool):
        return int(v)
    if not isinstance(v, Number):
        return 0
    part = v.split('.')[0]
    if not re.fullmatch(r'[+-]?[0-9]+', part):
        return 0
    n = int(part)
    return n if abs(n) <= 2**63 - 1 else 0


def get(v, key):
    if isinstance(v, Object):
        for k, x in v:
            if k == key:
                return x, True
    return None, False


def expected(text):
    value = load(text)
    lines = [quote(text), f'= {raw(value)}']
    if isinstance(value, Object):
        members = list(value)
    elif isinstance(value, list):
        members = [('', x) for x in value]
    else:
        members = []
    for i, (key, x) in enumerate(members):
        s = x if isinstance(x, str) and not isinstance(x, Number) else ''
        truth = 'true' if x is True else 'false'
        first = isinstance(value, Object) and next(j for j, (k, _) in enumerate(members) if k == key) == i
        lines.append(f'  {quote(key)} {raw(x)} {quote(s)} {integer(x)} {truth} {"true" if first else "false"}')
    found, has = get(value, 'id')
    params, _ = get(value, 'params')
    inner, inner_has = get(params, 'id')
    lines.append(f'  id {raw(found) if has else "null"} {raw(inner) if inner_has else "null"}')
    return lines


WORDS = ['', 'id', 'params', 'a', 'é', 'line', 'character', 'x y', 'tab\there', 'q"uote', 'back\\slash',
         'nul\0', 'bell\x07', 'cr\r\nlf', '😀', 'ﬁ', 'Ź', '{', '}', '[', ']', ':', ',']
NUMBERS = ['0', '-0', '7', '-7', '42', '1.5', '-2.75', '1e3', '1E-3', '-4.5e+10', '0.0001',
           '9223372036854775807', '-9223372036854775807', '9223372036854775808', '-9223372036854775808',
           '123456789012345678901234567890', '3.99', '-0.5']


def random_text(rng):
    word = rng.choice(WORDS)
    if rng.random() < 0.3:
        word += ''.join(chr(rng.choice([rng.randrange(1, 0x80), rng.randrange(0x80, 0xD800),
                                        rng.randrange(0xE000, 0x110000)])) for _ in range(rng.randrange(1, 6)))
    return word


def random_value(rng, depth):
    kind = rng.randrange(8 if depth < 5 else 5)
    if kind == 0:
        return random_text(rng)
    if kind == 1:
        return Number(rng.choice(NUMBERS))
    if kind == 2:
        return rng.choice([True, False])
    if kind == 3:
        return None
    if kind == 4:
        return Number(str(rng.randrange(-10**6, 10**6)))
    if kind in (5, 6):
        return [random_value(rng, depth + 1) for _ in range(rng.randrange(0, 5))]
    keys = ['id', 'params', 'method', 'uri'] + WORDS
    return Object((rng.choice(keys), random_value(rng, depth + 1)) for _ in range(rng.randrange(0, 6)))


def write(v, rng):
    """v as JSON text, with random spacing and escapes."""
    space = lambda: rng.choice(['', '', ' ', '\n', '\t ', '\r\n'])
    if isinstance(v, Number):
        return str(v)
    if isinstance(v, str):
        out = ['"']
        for ch in v:
            r = rng.random()
            if ch in '"\\' or ord(ch) < 32:
                out.append(json.dumps(ch)[1:-1] if r < 0.5 else f'\\u{ord(ch):04X}')
            elif r < 0.15:
                out.append(json.dumps(ch, ensure_ascii=True)[1:-1] if ord(ch) > 0x7F else f'\\u{ord(ch):04x}')
            elif r < 0.2 and ch == '/':
                out.append('\\/')
            else:
                out.append(ch)
        return ''.join(out + ['"'])
    if v is None or isinstance(v, bool):
        return json.dumps(v)
    if isinstance(v, Object):
        return '{' + space() + ','.join(f'{space()}{write(k, rng)}{space()}:{space()}{write(x, rng)}{space()}'
                                         for k, x in v) + '}'
    return '[' + space() + ','.join(f'{space()}{write(x, rng)}{space()}' for x in v) + ']'


FIXED = [
    '{"jsonrpc":"2.0","id":3,"method":"textDocument/hover","params":{"textDocument":{"uri":"file:///a.dewy"},'
    '"position":{"line":4,"character":12}}}',
    '{"id":"req-7","params":{"id":-1}}', '[]', '{}', '  [ ]  ', 'null', 'true', 'false', '"plain"', '17',
    '"\\ud83d\\ude00 \\ud800 x \\udc00 \\ud83d\\u0041 \\ud83dz"', '"\\u00e9\\u20ac\\b\\f\\/"',
    '{"a":1,"a":2,"b":{"a":3}}', '[1,[2,[3,[4]]]]', '{"id":null,"params":{"id":true}}',
]
MALFORMED = ['', ' ', 'garbage', '{', '[', '"open', '"\\', '"\\u12', '"\\u12"', '{"a":}', '{"a" 1}', '{a:1}',
             '[1,,2]', '[,]', '{,"a":1,}', '[1 2]', 'tru', 'nul', '-', '+', '.5', '1.2.3', '--1', '1e', 'é',
             '{"a":1}}', '[}', '{"x":[1,2}', '"\\q\\é"', '"\\ud800\\u"', '{"id":[1,{"id":2}],"params":{}} trailing']


def documents():
    rng = random.Random(20261024)
    valid = list(FIXED)
    for _ in range(300):
        valid.append(write(random_value(rng, 0), rng))
    malformed = list(MALFORMED)
    for text in valid[len(FIXED):len(FIXED) + 60]:
        cut = rng.randrange(0, len(text) + 1)
        malformed.append(text[:cut])
    return valid, malformed


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(binary, texts):
    ran = subprocess.run([binary, *texts], capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_json_doc_matches_jo(compiler, tmp_path, release):
    valid, malformed = documents()
    dewy = build(compiler, FIXTURES / 'json_doc_dewy.dewy', tmp_path / 'json-dewy', release)
    jo = build(compiler, FIXTURES / 'json_doc_jo.jo', tmp_path / 'json-jo', release)
    for texts in (valid, malformed):
        assert run(dewy, texts) == run(jo, texts)
    want = [line for text in valid for line in expected(text)]
    assert run(dewy, valid).decode().split('\n')[:-1] == want


@pytest.mark.core_quick
def test_selfhost_json_doc_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/json_doc.dewy\0' in binary
    assert b'/compiler/json_doc.jo\0' not in binary
