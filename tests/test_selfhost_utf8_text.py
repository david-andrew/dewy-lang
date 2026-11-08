"""compiler/utf8_text.dewy, the UTF-8 walk of the prompt's line editor and the language server's writer: it
ships, and its frozen implementation-language twin compiler/utf8_text.jo gives the same answers. The oracle is
Python's decoder: invalid text is replaced by U+FFFD for each maximal subpart (as WHATWG and Unicode say), and
characters are whole valid sequences or single bytes."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/selfhost'
SAMPLES = [b'', b'a', b'abc', 'é'.encode(), '中'.encode(), '😀'.encode(), 'éx'.encode(), b'\x80', b'\xbf\xbf',
           b'\xc3', b'\xe4\xb8', b'\xf0\x9f\x98', b'\xc0\x80', b'\xc1\xbf', b'\xe0\x80\x80', b'\xe0\xa0\x80',
           b'\xed\xa0\x80', b'\xed\x9f\xbf', b'\xf0\x80\x80\x80', b'\xf0\x90\x80\x80', b'\xf4\x8f\xbf\xbf',
           b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80', b'\xf8\x88\x80\x80\x80', b'\xff\xfe', b'a\xc3b',
           b'\xe4\xb8x', b'\xf0\x9f\x98\x80\xf0\x9f', b'\xc3\xa9\x80\xe4\xb8\xad']


def whole(data, i):
    """The length of the valid character at i, or 0."""
    for size in (1, 2, 3, 4):
        try:
            if len(data[i:i + size].decode('utf-8')) == 1:
                return size
        except UnicodeDecodeError:
            pass
    return 0


def expected(data):
    ends, at = [], 0
    while at < len(data):
        at += whole(data, at) or 1
        ends.append(at)
    starts, prev = [], 0
    for end in ends:
        starts.append(prev)
        prev = end
    boundaries = [0] + ends
    floors = [max(b for b in boundaries if b <= i) for i in range(len(data) + 1)]
    if boundaries[-1] != len(data):
        floors = floors[:-1] + [len(data)]
    lines = [f'clean {data.decode("utf-8", "replace").encode().hex()}']
    for name, values in (('next', ends), ('prev', starts), ('floor', floors)):
        lines.append(name + ''.join(f' {v}' for v in values))
    return lines


def samples():
    rng = random.Random(7)
    pool = [b'a', b'\x80', b'\xbf', b'\xc3', b'\xa9', b'\xe4', b'\xb8', b'\xad', b'\xf0', b'\x9f', b'\x98', b'\xed',
            b'\xa0', b'\xf4', b'\x90', b'\xff', b'\xe0', b'\xc0']
    return SAMPLES + [b''.join(rng.choice(pool) for _ in range(rng.randint(1, 9))) for _ in range(300)]


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def run(binary, texts):
    ran = subprocess.run([binary, *texts], capture_output=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_utf8_text_matches_jo(compiler, tmp_path, release):
    texts = [s for s in samples() if s]  # (an empty argument is not one a shell can pass on every host)
    dewy = build(compiler, FIXTURES / 'utf8_text_dewy.dewy', tmp_path / 'utf8-dewy', release)
    jo = build(compiler, FIXTURES / 'utf8_text_jo.jo', tmp_path / 'utf8-jo', release)
    got = run(dewy, texts)
    assert got == run(jo, texts)
    want = [line for text in texts for line in expected(text)]
    assert got.decode().split('\n')[:-1] == want


def test_selfhost_utf8_text_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/utf8_text.dewy\0' in binary
    assert b'/compiler/utf8_text.jo\0' not in binary
