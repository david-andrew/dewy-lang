"""compiler/intern.dewy (the compiler's names: a name's hash, its id found by its bytes, a new
name's id): it ships, and its frozen implementation-language twin compiler/intern.jo gives the
same answers. One Sloppy driver runs over either module on random rounds of interning: names
of any bytes (malformed UTF-8 and NUL included), equal names at different places, lookups of
names never added, every length to a few words, and a round past 8192 names, where the table
grows. The oracle below hashes in Python and keeps the table as Python lists."""
import functools
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/intern_jo.jo'
M = 1 << 64


def signed(v):
    return v - M if v >= 1 << 63 else v


def word(b, at, size):
    return int.from_bytes(b[at:at + size], 'little')


def hash_bytes(b):
    """compiler/intern.dewy's hash_bytes"""
    n = len(b)
    h = n * 0x9E3779B97F4A7C15 % M
    if n > 8:
        i = 0
        while i + 8 < n:
            h = (h ^ word(b, i, 8)) * 0xBF58476D1CE4E5B9 % M
            h ^= h >> 31
            i += 8
        h ^= word(b, n - 8, 8)
    elif n >= 4:
        h ^= word(b, 0, 4) ^ (word(b, n - 4, 4) << 32)
    elif n > 0:
        h ^= b[0] ^ (b[n >> 1] << 8) ^ (b[n - 1] << 16)
    h = h * 0xBF58476D1CE4E5B9 % M
    return signed(h ^ (h >> 32))


class Oracle:
    """ids in the order names are first seen (0 is ""), and the slots as linear probing places them"""

    def __init__(self, wraps):
        self.names, self.hashes, self.slots, self.ids = [], [], [], {}
        self.wraps = wraps      # (the table sizes where a probe went past the end)

    def place(self, h, k):
        mask = len(self.slots) - 1
        i = h & mask
        while self.slots[i] != 0:
            if i == mask:
                self.wraps.add(len(self.slots))
            i = (i + 1) & mask
        self.slots[i] = k + 1

    def find(self, b):
        return self.ids.get(b, -1) if self.slots else -1

    def intern(self, b):
        if self.find(b) >= 0:
            return self.ids[b]
        if not self.slots:
            self.slots = [0] * (1 << 14)
            self.add(b'')
            if b == b'':
                return 0
        return self.add(b)

    def add(self, b):
        k = len(self.names)
        self.names.append(b)
        self.hashes.append(hash_bytes(b))
        self.ids[b] = k
        self.place(self.hashes[k], k)
        if len(self.names) * 2 > len(self.slots):
            self.slots = [0] * (len(self.slots) * 2)
            for j, h in enumerate(self.hashes):
                self.place(h, j)
        return k

    def dump(self):
        checksum = signed(sum((i + 1) * e for i, e in enumerate(self.slots)) % M)
        out = [f'{len(self.names)} {len(self.slots)} {checksum}']
        out += [f'{k} {h} [{", ".join(map(str, b))}]' for k, (h, b) in enumerate(zip(self.hashes, self.names))]
        return out


@functools.cache
def corpus(seed):
    """(blob, steps, the answers the oracle gives, the table sizes where a probe wrapped)"""
    rng = random.Random(seed)
    blob = bytearray()
    spans = []      # (start, length) of each name written into the blob

    def piece(b):
        spans.append((len(blob), len(b)))
        blob.extend(b)
        return spans[-1]

    def fresh():
        n = rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 24, 31, 33, rng.randrange(1, 40), rng.randrange(40, 300)])
        r = rng.random()
        if r < 0.4:
            alphabet = b'abcdefghijklmnopqrstuvwxyz_0123456789'
            return bytes(rng.choice(alphabet) for _ in range(n))
        if r < 0.6:
            # (malformed UTF-8: continuation bytes first, lone leads, overlongs, NUL)
            return bytes(rng.choice([0x80, 0xbf, 0xc0, 0xc3, 0xe2, 0xf0, 0xff, 0x00, 0x61]) for _ in range(n))
        if r < 0.75:
            return ''.join(rng.choice('aé→🙂_') for _ in range(max(1, n // 3))).encode()
        return bytes(rng.randrange(256) for _ in range(n))

    def landing(mask):
        """a new name whose first slot is the table's last: its probe wraps to the start"""
        while True:
            b = bytes(rng.choice(b'abcdefghijklmnopqrstuvwxyz') for _ in range(7))
            if hash_bytes(b) & mask == mask:
                return b

    lines, want, wraps = [], [], set()
    rounds = [rng.randrange(50, 600) for _ in range(24)] + [20000]
    for size in rounds:
        o = Oracle(wraps)
        lines.append('R')
        seen = []
        ends = 0
        for _ in range(size):
            r = rng.random()
            if r < 0.45 or not seen:
                # (a few names at the end of the table, so probes wrap: before and after it grows)
                end = o.slots and ends < 3 + len(o.slots) // 8192 and rng.random() < 0.01
                ends += bool(end)
                b = landing(len(o.slots) - 1) if end else fresh()
                start, n = piece(b)
                op = 'S' if rng.random() < 0.15 else 'I'
                lines.append(f'{op} {start} {n}')
                want.append(str(o.intern(b)))
                seen.append(b)
                if end:
                    # (and every name at the end found again, by a probe that may wrap)
                    for k in range(len(seen) - 1, -1, -1):
                        if hash_bytes(seen[k]) & (len(o.slots) - 1) == len(o.slots) - 1:
                            start, n = piece(seen[k])
                            lines.append(f'F {start} {n}')
                            want.append(str(o.find(seen[k])))
            elif r < 0.75:
                # (the same name again, at another place in the blob; or where it was)
                b = rng.choice(seen)
                start, n = piece(b) if rng.random() < 0.5 else spans[rng.randrange(len(spans))]
                b = bytes(blob[start:start + n])
                lines.append(f'I {start} {n}')
                want.append(str(o.intern(b)))
            elif r < 0.85:
                # (a lookup: a name seen, or one never added, maybe one byte off a name)
                b = rng.choice(seen)
                if rng.random() < 0.5 and b:
                    k = rng.randrange(len(b))
                    b = b[:k] + bytes([b[k] ^ 1]) + b[k + 1:]
                start, n = piece(b)
                lines.append(f'F {start} {n}')
                want.append(str(o.find(b)))
            elif r < 0.93:
                start, n = spans[rng.randrange(len(spans))]
                lines.append(f'H {start} {n}')
                want.append(str(hash_bytes(bytes(blob[start:start + n]))))
            else:
                b = rng.choice(seen)
                c = b
                if b and rng.random() < 0.6:
                    k = rng.randrange(len(b))
                    c = b[:k] + bytes([b[k] ^ (1 << rng.randrange(8))]) + b[k + 1:]
                x, _ = piece(b)
                y, _ = piece(c)
                lines.append(f'Q {x} {y} {len(b)}')
                want.append('1' if b == c else '0')
        lines.append('D')
        want += o.dump()
    return bytes(blob), '\n'.join(lines) + '\n', f'{len(blob)}\n' + '\n'.join(want) + '\n', wraps


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_intern_matches_jo(compiler, tmp_path, release):  # noqa: F811
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/intern.jo'"
    assert twin in driver
    blob, steps, want, _ = corpus(23)
    (tmp_path / 'blob').write_bytes(blob)
    (tmp_path / 'steps').write_text(steps)
    outputs = []
    for module in ('intern.dewy', 'intern.jo'):
        source = tmp_path / f'driver-{module.replace(".", "-")}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'"))
        binary = build(compiler, source, tmp_path / source.stem, release)
        ran = subprocess.run([binary, tmp_path / 'blob', tmp_path / 'steps'], capture_output=True, text=True,
                             timeout=120)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    for got, expected in zip(outputs[0].split('\n'), want.split('\n')):
        assert got == expected
    assert outputs[0] == want


def test_corpus_reaches_every_step():
    blob, steps, want, wraps = corpus(23)
    ops = [line.split(' ')[0] for line in steps.split('\n') if line]
    for op in 'ISFHQ':
        assert ops.count(op) >= 200, op
    assert ops.count('R') == ops.count('D') == 25
    # (lookups that miss, spans that differ, the table grown past its first size)
    answers = want.split('\n')
    assert answers.count('-1') >= 100 and answers.count('0') >= 100
    assert any(line.split(' ')[1:2] == ['32768'] for line in answers if line.count(' ') == 2)
    assert any(b >= 0x80 for b in blob) and 0 in blob
    # (probes past the table's end, before and after it grows)
    assert wraps == {1 << 14, 1 << 15}


@pytest.mark.core_quick
def test_selfhost_intern_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/intern.dewy\0' in binary
    assert b'/compiler/intern.jo\0' not in binary
