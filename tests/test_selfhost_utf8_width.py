"""compiler/utf8_text.dewy's terminal column widths, and its frozen twin utf8_text.jo, against a wcwidth-style
rule computed from Python's unicodedata: marks, format characters and combining characters take no column, East
Asian Wide and Fullwidth characters two, the rest one, and an invalid byte one."""
import random
import unicodedata

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_utf8_text import FIXTURES, build, run

TABLE_VERSION = '17.0.0'  # (the Unicode version the committed tables were generated from)


def width(cp):
    ch = chr(cp)
    if cp < 0x80:
        return 1
    if cp == 0xAD:  # (the soft hyphen is drawn: one column)
        return 1
    if unicodedata.category(ch) in ('Mn', 'Me', 'Cf') or unicodedata.combining(ch) or cp <= 0x9F:
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1


def scalar(cp):
    return not 0xD800 <= cp <= 0xDFFF


# characters whose class is the same in every Unicode version since 9
FIXED = ['a', 'Z', ' ', '~', '\x7f', '\x80', '\x9f', ' ', 'é', '­', '́', 'ͯ', '҃', 'ß',
         'ְ', 'ا', 'ً', '​', '‍', '‎', ' ', '⁠', '⃐', '〈',
         '〉', '⌚', '☔', '☕', '✅', '❤', '️', 'ᄀ', 'ᅟ', 'ᅠ',
         '⺀', '　', '、', '〿', 'ぁ', 'ァ', 'ㄅ', '㄰', 'ㄱ', 'ꥠ',
         '가', '힣', '豈', '︐', '︰', '﹫', '﻿', '！', '｠', '｡',
         '￠', '￦', '￨', '\U0001f300', '\U0001f600', '😀', '\U0001f9d1', '\U0001f1e6', '中',
         '\U00020000', '\U0002fffd', '\U00030000', '\U000e0001', '\U000e0100', '\U0001d167', '\U0001f004']


def boundaries():
    """The first and last code point of every run of one width, and their neighbours."""
    points, last = [], None
    for cp in range(0x80, 0x110000):
        if not scalar(cp):
            continue
        w = width(cp)
        if w != last:
            points += [cp - 1, cp]
            last = w
    return [cp for cp in points if cp >= 0x80 and scalar(cp)]


def texts(full):
    chars = [ord(c) for c in FIXED]
    if full:
        rng = random.Random(11)
        chars += boundaries() + [rng.randrange(0x80, 0x110000) for _ in range(1500)]
    chars = [cp for cp in chars if scalar(cp)]
    words = [''.join(map(chr, chars[i:i + 8])).encode() for i in range(0, len(chars), 8)]
    words += [b'e\xcc\x81', b'\xe4\xb8', b'\x80\xe4\xb8\xad', b'\xf0\x9f\x98', b'\xc3', b'\xff\xe4\xb8\xadx']
    return words


def expected(data):
    out, i = [], 0
    while i < len(data):
        for size in (1, 2, 3, 4):
            try:
                if len(data[i:i + size].decode('utf-8')) == 1:
                    out.append(width(ord(data[i:i + size].decode('utf-8'))))
                    i += size
                    break
            except UnicodeDecodeError:
                pass
        else:
            out.append(1)
            i += 1
    return 'w' + ''.join(f' {w}' for w in out)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_utf8_width_matches_unicodedata(compiler, tmp_path, release):
    # (the whole range is compared only where Python's Unicode version is the tables')
    words = texts(unicodedata.unidata_version == TABLE_VERSION)
    dewy = build(compiler, FIXTURES / 'utf8_width_dewy.dewy', tmp_path / 'width-dewy', release)
    jo = build(compiler, FIXTURES / 'utf8_width_jo.jo', tmp_path / 'width-jo', release)
    got = run(dewy, words)
    assert got == run(jo, words)
    assert got.decode().split('\n')[:-1] == [expected(w) for w in words]


def test_selfhost_utf8_width_known_widths(compiler, tmp_path):
    dewy = build(compiler, FIXTURES / 'utf8_width_dewy.dewy', tmp_path / 'width-dewy', False)
    words = ['a中😀é'.encode(), 'é'.encode(), 'ｱＡ'.encode(), '‍️'.encode()]
    assert run(dewy, words).decode().split('\n')[:-1] == ['w 1 2 2 1', 'w 1 0', 'w 1 2', 'w 0 0']
