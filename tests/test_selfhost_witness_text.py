"""Cold witness formatting preserves bytes and endpoint candidate behavior."""
import random
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MIN, MAX = -(1 << 63), (1 << 63) - 1


def signed(value):
    return (value - MIN) % (1 << 64) + MIN


def known(lo, hi, wide, unsigned):
    if unsigned:
        a, b = lo - MIN, hi - MIN
        left, right = lo != MIN, hi != MAX
    else:
        if wide and lo == hi and lo in (MIN, MAX):
            return f'is at {"most" if lo == MIN else "least"} {lo}'
        a, b = lo, hi
        left, right = lo > -(1 << 62), hi < (1 << 62)
    if lo == hi:
        return f'is {a}'
    if left and right:
        return f'is between {a} and {b}'
    if left:
        return f'is at least {a}'
    if right:
        return f'is at most {b}'
    return ''


def corpus():
    rng = random.Random(3328)
    blob, steps, expected = bytearray(), [], []
    texts = [b'', b'$', b'plain', b'__s', b'__s0', b'__s9x', b'__size', b'__k1',
             b'__ix2', b'__each3', b'__has4', b'__index5', b'__index\xff',
             b'__s\xc2\xb2', b'__s\x00', b'__s\x809', b'"', b'\\', b'{', b'}']
    texts += [bytes([c]) for c in range(256)]
    texts += [bytes(rng.randrange(256) for _ in range(rng.randrange(40))) for _ in range(300)]
    texts += [bytes(rng.randrange(32, 127) for _ in range(rng.randrange(40))) for _ in range(300)]
    for text in texts:
        at = len(blob)
        blob += text
        steps += [f'H {at} {len(text)}', f'Q {at} {len(text)}']
        hidden = bool(re.match(rb'^(?:\$|__(?:s|k|ix|each|has|index)[0-9])', text))
        quote = not any(c < 32 or c > 126 or c in b'"\\{}' for c in text)
        expected += [str(hidden).lower(), '"' + text.decode('ascii') + '"' if quote else '']
    ends = [MIN, MIN + 1, -(1 << 62), -(1 << 62) + 1, -1, 0, 1,
            (1 << 62) - 1, 1 << 62, MAX - 1, MAX]
    bounds = [(a, b) for a in ends for b in ends if a <= b]
    bounds += [tuple(sorted([rng.randint(MIN, MAX), rng.randint(MIN, MAX)])) for _ in range(300)]
    for lo, hi in bounds:
        for wide in (0, 1):
            for flag in (0, 1):
                steps += [f'K {lo} {hi} {wide} {flag}', f'C {lo} {hi} {flag} {wide}']
                choices = []
                if not (wide and lo == hi and lo in (MIN, MAX)):
                    for value in (0, 1, -1, lo, hi, signed(lo + 1), signed(hi - 1)):
                        if lo <= value <= hi and not (flag and value == 0) and value not in choices:
                            choices.append(value)
                expected += [known(lo, hi, wide, flag), str(choices)]
    for value in ends:
        steps.append(f'O {value}')
        expected.append(f' + {value}' if value > 0 else f' - {signed(-value)}' if value < 0 else '')
    return bytes(blob), '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_witness_text_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    blob, steps, expected = corpus()
    (tmp_path / 'blob').write_bytes(blob)
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/witness_text_jo.jo').read_text()
    for module in ('witness_text.dewy', 'witness_text.jo'):
        source, binary = tmp_path / f'{module}.jo', tmp_path / f'{module}.bin'
        source.write_text(driver.replace('../../../compiler/witness_text.jo', str(ROOT / 'compiler' / module)))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'blob', tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_witness_text_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/witness_text.dewy\0' in binary
    assert b'/compiler/witness_text.jo\0' not in binary
