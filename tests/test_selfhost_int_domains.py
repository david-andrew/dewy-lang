"""The shipped integer-domain engine and its bootstrap twin against a set oracle.

Replay write histories, not compiler-generated expectations. The oracle collects
all bindings eagerly, then filters by requested capture ancestry; the engine
scans a flat log backwards and forwards and never builds undemanded states.
"""
from dataclasses import dataclass, field
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/int_domains_jo.jo'
MIN, MAX = -(1 << 63), (1 << 63) - 1
DECL, POINT, OPEN, DELTA, CAPTURE = range(5)


def intervals(values):
    pairs = []
    for value in sorted(values):
        if pairs and pairs[-1][1] + 1 == value:
            pairs[-1][1] = value
        else:
            pairs.append([value, value])
    return pairs


@dataclass
class Domain:
    site: int = -2
    source: int = 0
    open: bool = False
    points: set = field(default_factory=set)
    deltas: list = field(default_factory=list)


class Oracle:
    def __init__(self):
        self.states = {}
        self.ancestry = {}

    def write(self, binding, kind, a=0, b=0):
        if kind == DECL:
            self.states[binding] = Domain(site=a)
        elif kind == CAPTURE:
            self.ancestry.setdefault(binding, set()).add(a)
            if a in self.states:
                self.states[binding] = Domain(site=-1, source=a)
        elif binding in self.states:
            d = self.states[binding]
            if kind == POINT:
                d.points.add(a)
            elif kind == OPEN:
                d.open = True
            elif kind == DELTA:
                if d.site < 0 or d.site != b or len(d.deltas) >= 8:
                    d.open = True
                else:
                    d.deltas.append(a)

    def demanded(self, requests):
        reached = set(requests)
        pending = list(requests)
        while pending:
            for parent in self.ancestry.get(pending.pop(), ()):
                if parent not in reached:
                    reached.add(parent)
                    pending.append(parent)
        return reached & self.states.keys()

    def values(self, binding, depth=0):
        if binding not in self.states or depth > 64:
            return set()
        d = self.states[binding]
        if d.open:
            return set()
        values = set(d.points)
        if d.source:
            source = self.values(d.source, depth + 1)
            if not source:
                return set()
            for lo, hi in intervals(source):
                if hi - lo >= 256:
                    return set()
                # Existing twin behavior: a captured run ending at MAX has a
                # wrapped exclusive end and contributes no values. Preserve
                # it in this translation; changing semantics is out of scope.
                if hi != MAX:
                    values.update(range(lo, hi + 1))
        if not values:
            return set()
        for delta in d.deltas:
            added = {v + delta for v in values}
            if any(v < MIN or v > MAX for v in added):
                return set()
            values |= added
            if len(values) > 256:
                return set()
        return values


def corpus():
    steps, expected = [], []

    def case(writes, demands, queries=None):
        oracle = Oracle()
        steps.append('R')
        for write in writes:
            binding, kind, a, b = (*write, *([0] * (4 - len(write))))
            steps.append(f'W {binding} {kind} {a} {b}')
            oracle.write(binding, kind, a, b)
        steps.extend(f'D {b}' for b in demands)
        steps.append('S')
        live = oracle.demanded(demands)
        expected.append(f'states {len(live)}')
        if queries is None:
            queries = sorted({w[0] for w in writes} | set(demands))
        # Repeated reads in reverse order must not mutate a parent through COW.
        queries = list(queries)
        for binding in queries + queries[::-1]:
            steps.append(f'Q {binding}')
            if binding not in live:
                expected.append('absent')
            else:
                pairs = intervals(oracle.values(binding))
                flat = [v for pair in pairs for v in pair]
                text = '|'.join(str(a) if a == b else f'{a}..{b}' for a, b in pairs)
                expected.append(f'{flat} {text}')

    case([], [1])
    case([(1, POINT, 3), (1, OPEN), (2, DELTA, 1, 0), (3, CAPTURE, 1)], [1, 2, 3])
    case([(1, DECL, 4), (1, POINT, 3), (1, POINT, 3), (1, POINT, 4),
          (1, POINT, 9), (2, DECL), (2, POINT, 8)], [1])
    for point, delta in [(MIN, -1), (MAX, 1), (MIN, 1), (MAX, -1), (0, MIN), (0, MAX)]:
        case([(1, DECL, 0), (1, POINT, point), (1, DELTA, delta, 0)], [1])
    for n in (8, 9):
        case([(1, DECL, 4), (1, POINT, 0)] + [(1, DELTA, 1 << i, 4) for i in range(n)], [1])
    for size in (255, 256, 257, 300):
        writes = [(1, DECL, 4)] + [(1, POINT, i) for i in range(size)]
        case(writes + [(2, CAPTURE, 1)], [2])
        case(writes + [(1, DELTA, 0, 4)], [1])
    for site, where in [(-1, -1), (4, 5), (4, 4)]:
        case([(1, DECL, site), (1, POINT, 3), (1, DELTA, 2, where)], [1])
    for n in (64, 65, 66):
        case([(1, DECL, 0), (1, POINT, -10)] + [(i, CAPTURE, i - 1) for i in range(2, n + 1)], [n])
    for point in (MIN, MAX, 5):
        case([(1, DECL, 0), (1, POINT, point), (2, CAPTURE, 1), (2, POINT, 7), (1, POINT, 6)], [2])
    case([(1, DECL, 0), (1, POINT, 3), (2, CAPTURE, 1), (1, OPEN)], [2])
    # No consumer means no state, even for a long write history.
    case([(1, DECL, 0)] + [(1, POINT, i) for i in range(1000)], [])
    case([(-3, DECL, -1), (-3, POINT, 7), (1, CAPTURE, -3),
          (-3, POINT, 9), (2, DECL, 4), (2, POINT, 1), (2, DECL, 5),
          (2, POINT, 8), (2, DELTA, 2, 5)], [1, 2])
    rng = random.Random(2906)
    for _ in range(160):
        writes = []
        for binding in range(1, 31):
            site = rng.randrange(-1, 8)
            if binding > 1 and rng.random() < .3:
                writes.append((binding, CAPTURE, rng.randrange(1, binding)))
            else:
                writes.append((binding, DECL, site))
                writes.append((binding, POINT, rng.randrange(-20, 21)))
            for _ in range(rng.randrange(10)):
                kind = rng.choices([POINT, OPEN, DELTA], [8, 1, 5])[0]
                writes.append((binding, kind, rng.randrange(-10, 11), site))
            # A source can change after the value capture is created.
            if binding > 1:
                writes.append((rng.randrange(1, binding), POINT, rng.randrange(-30, 31)))
        case(writes, rng.sample(range(1, 31), rng.randrange(31)))
    return '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_int_domains_matches_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    commands = tmp_path / 'steps'
    commands.write_text(steps)
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/int_domains.jo'"
    outputs = []
    for module in ('int_domains.dewy', 'int_domains.jo'):
        source = tmp_path / f'{module}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'"))
        binary = tmp_path / f'{module}.bin'
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, commands], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    for row, (got, want) in enumerate(zip(outputs[0].splitlines(), expected.splitlines())):
        assert got == want, f'output row {row}'
    assert outputs[0] == expected


@pytest.mark.core_quick
def test_selfhost_int_domains_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/int_domains.dewy\0' in binary
    assert b'/compiler/int_domains.jo\0' not in binary
