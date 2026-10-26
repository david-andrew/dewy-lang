"""Refinement/match interval algebra against an independent split/set oracle."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MIN, MAX = -(1 << 63), (1 << 63) - 1


def runs(values):
    out = []
    for v in sorted(set(values)):
        if out and out[-1][1] + 1 == v:
            out[-1][1] = v
        else:
            out.append([v, v])
    return out


def subtract(want, have):
    # Split each desired piece by every cover, without sorting the covers.
    out = []
    for lo, hi in want:
        pieces = [[lo, hi]]
        for a, b in have:
            next_pieces = []
            for x, y in pieces:
                if b < x or a > y:
                    next_pieces.append([x, y])
                else:
                    if x < a:
                        next_pieces.append([x, a - 1])
                    if b < y:
                        next_pieces.append([b + 1, y])
            pieces = next_pieces
        out += pieces
    return out


def flat(pairs):
    return [v for pair in pairs for v in pair]


def rendered(pairs):
    words = []
    for lo, hi in pairs[:4]:
        if lo == hi:
            words.append(str(lo))
        elif lo == MIN:
            words.append(f'values up to {hi}')
        elif hi == MAX:
            words.append(f'values from {lo}')
        else:
            words.append(f'{lo} through {hi}')
    if len(pairs) > 4:
        words.append('...')
    return f'{flat(pairs)}|' + ', '.join(words)


def corpus():
    commands, expected = [], []

    def gap(lo, hi, excluded):
        commands.append('G ' + ' '.join(map(str, [lo, hi, *excluded])))
        expected.append(rendered(subtract([[lo, hi]] if lo <= hi else [], [[v, v] for v in excluded])))

    def pair(op, a, b):
        commands.append(op + ' ' + ' '.join(map(str, [len(flat(a)), *flat(a), *flat(b)])))
        if op == 'D':
            result = subtract(a, b)
        else:
            result = [[max(lo, x), min(hi, y)] for lo, hi in a for x, y in b if max(lo, x) <= min(hi, y)]
        expected.append(rendered(result))

    gap(MIN, MAX, [MIN, MAX, 0, 0, -1, 1])
    gap(MAX, MIN, [])
    for lo, hi in [(MIN, MIN), (MAX, MAX), (MIN, MIN + 3), (MAX - 3, MAX), (-3, 3)]:
        gap(lo, hi, [])
        gap(lo, hi, [lo, hi, lo])
        for covers in ([], [[MIN, MAX]], [[lo, hi]], [[hi, hi], [lo, lo]], [[MIN, 0], [0, MAX]]):
            pair('D', [[lo, hi]], covers)
    rng = random.Random(3308)
    for _ in range(500):
        origin = rng.choice([MIN + 32, -15, MAX - 32])
        a = runs(origin + rng.randrange(30) for _ in range(rng.randrange(35)))
        b = runs(origin + rng.randrange(30) for _ in range(rng.randrange(35)))
        pair('M', a, b)
        pair('D', a, b)
        unsorted = [sorted([origin + rng.randrange(30), origin + rng.randrange(30)]) for _ in range(rng.randrange(10))]
        pair('D', a, unsorted)
        pair('A', unsorted, b)
        gap(origin, origin + 29, [origin + rng.randrange(-5, 35) for _ in range(rng.randrange(40))])
    for pairs in ([], [[MIN, MIN]], [[MAX, MAX]], [[MIN, MAX]], [[i, i] for i in range(6)]):
        commands.append(' '.join(['T', *map(str, flat(pairs))]))
        expected.append(rendered(pairs))
    return '\n'.join(commands) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_intervals_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/intervals_jo.jo').read_text()
    for module in ('intervals.dewy', 'intervals.jo'):
        source, binary = tmp_path / f'{module}.jo', tmp_path / f'{module}.bin'
        source.write_text(driver.replace('../../../compiler/intervals.jo', str(ROOT / 'compiler' / module)))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_intervals_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/intervals.dewy\0' in binary
    assert b'/compiler/intervals.jo\0' not in binary
