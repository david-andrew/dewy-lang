"""compiler/literals.dewy's literal_string_text (a string's text decoded up to its next
interpolation, which dewy_fast.jo's dn_string reads for both parsers) and its frozen twin in
compiler/literals.jo give the same bytes, stopping place and mistake. One Sloppy driver runs over
either module, in default and release builds, on every double-quoted string of the repository's
Dewy sources (from its start and after each interpolation) and on generated texts: escapes
good and bad, braces, malformed UTF-8 and NUL, and spans that start or stop anywhere. The oracle
reads the text byte by byte, with test_selfhost_literals.py's escape rules."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_literals import BAD, GOOD, Problem, escape

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/string_text_jo.jo'
TWIN = "use '../../../compiler/literals.jo'"
QUOTED = re.compile(rb'"(?:[^"\\\n]|\\.)*"')


def oracle(s, i, stop):
    """the bytes, where it stopped, and the mistake (the driver's line)"""
    out = bytearray()
    while i < stop:
        if s[i] == ord('{'):
            break
        if s[i] == ord('\\'):
            try:
                i = escape(out, s, i, stop)
            except Problem as p:
                message, at = p.args[0], int(p.text.rsplit(b' ', 2)[1][1:])
                message = message if isinstance(message, bytes) else message.encode()
                return b'%s %d ! %s @%d false' % (out.hex().encode(), stop, message.hex().encode(), at)
            continue
        out.append(s[i])
        i += 1
    return b'%s %d' % (out.hex().encode(), i)


def closing(s, i):
    """past the brace closing the interpolation opened at s[i] (depth only: any place will do)"""
    depth = 0
    while i < len(s):
        depth += {ord('{'): 1, ord('}'): -1}.get(s[i], 0)
        i += 1
        if depth == 0:
            return i
    return len(s)


def corpus():
    """(text, start, stop): each double-quoted string's text, read from its start and after each
    interpolation"""
    files = subprocess.run(['git', 'ls-files', '-z', '*.dewy'], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split('\0')[:-1]
    out = []
    for name in files:
        for m in QUOTED.finditer((ROOT / name).read_bytes()):
            s = m.group(0)
            i, stop = 1, len(s) - 1
            while i <= stop:
                out.append((s, i, stop))
                j = s.find(b'{', i, stop)
                if j < 0:
                    break
                i = closing(s, j)
    return out


def generated(rng):
    pieces = GOOD + BAD + [b'{', b'}', b'{x}', b'\\', b'\x00', b'\x80', b'\xff', b'\xf0\x9f', 'é'.encode(), b'"']
    out = []
    for _ in range(3000):
        s = b''.join(rng.choice(pieces) for _ in range(rng.randrange(0, 12)))
        if rng.random() < 0.3:
            s += bytes(rng.randrange(256) for _ in range(rng.randrange(0, 6)))
        n = len(s)
        start = rng.choice([0, 0, rng.randrange(n + 1)])
        stop = rng.choice([n, n, rng.randrange(n + 1)])
        out.append((s, start, stop))
    return out


def records():
    rng = random.Random(20261024)
    return corpus() + generated(rng)


def test_corpus_reaches_every_ending():
    seen = set()
    for s, i, stop in records():
        line = oracle(s, i, stop)
        seen.add('mistake' if b' ! ' in line else 'brace' if int(line.split(b' ')[1]) < stop else 'end')
    assert seen == {'mistake', 'brace', 'end'}


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_string_text_match_jo(compiler, tmp_path, release):
    rows = records()
    data = tmp_path / 'texts'
    data.write_bytes(b''.join(b'%s %d %d\n' % (s.hex().encode(), i, stop) for s, i, stop in rows))
    want = b''.join(oracle(s, i, stop) + b'\n' for s, i, stop in rows)
    driver = DRIVER.read_text()
    assert TWIN in driver
    for module in ('literals.jo', 'literals.dewy'):
        source = tmp_path / f'string_text_{module.replace(".", "_")}.jo'
        source.write_text(driver.replace(TWIN, f"use '{ROOT / 'compiler' / module}'"))
        binary = tmp_path / source.stem
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, data], capture_output=True, timeout=120)
        assert ran.returncode == 0, ran.stderr
        got = ran.stdout.splitlines(keepends=True)
        for k, (line, expected) in enumerate(zip(got, want.splitlines(keepends=True))):
            assert line == expected, (module, rows[k])
        assert len(got) == len(rows), module
