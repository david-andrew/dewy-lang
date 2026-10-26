"""Finite-key queries retain ordering, interval budgets and partial failures."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MIN, MAX = -(1 << 63), (1 << 63) - 1


def corpus():
    rng = random.Random(3630)
    lines, expected = [], []
    types = [('open',), ('open',), ('open',)]
    sets = [[]]

    def add(kind, *data):
        types.append((kind, *data))
        return len(types) - 1

    def strings(values):
        lines.append('S ' + ','.join(values))
        sets.append(list(values))
        return add('strings', len(sets) - 1)

    def integer(lo, hi, gaps=()):
        lines.append(f'I {lo} {hi} {",".join(map(str, gaps)) or "-"}')
        return add('integer', lo, hi, list(gaps))

    def union(children):
        lines.append('U ' + (','.join(map(str, children)) or '-'))
        return add('union', list(children))

    def values(t, math=False):
        node = types[t]
        if node[0] == 'strings':
            return True, [f"'{v}'" for v in sets[node[1]]]
        if node[0] == 'alias':
            return values(node[1], math)
        if node[0] == 'union':
            out = []
            for child in node[1]:
                ok, keys = values(child, math)
                if not ok:
                    return False, out
                out.extend(keys)
            return True, out
        if node[0] == 'integer' and not math:
            lo, hi, gaps = node[1:]
            # Materialize the bounded test domain, then group adjacent points;
            # the production budget applies independently to each run.
            points = [v for v in range(lo, hi + 1) if v not in gaps]
            runs = []
            for v in points:
                if runs and runs[-1][-1] + 1 == v:
                    runs[-1].append(v)
                else:
                    runs.append([v])
            out = []
            for run in runs:
                if len(run) > 4097:
                    return False, out
                out.extend(map(str, run))
            return True, out
        return False, []

    def query(t, math=False):
        lines.append(f'Q {t} {1 if math else 0}')
        ok, keys = values(t, math)
        expected.append(f'{str(ok).lower()} {"|".join(keys)}')

    words = strings(['north', 'south', 'east', 'west'])
    strings(['é', "a'b", '', '0b'])
    repeated = strings(['x', 'x'])
    a = integer(-3, 3, [0, 0, -2, 20])
    b = integer(MAX - 2, MAX)
    c = integer(MIN, MIN + 2)
    for t in (0, 1, 2, words, repeated, a, b, c, union([]), union([words, a, b, c]), union([a, words, 1, b])):
        query(t)
    lines.append(f'V {words}')
    alias = add('alias', words)
    query(alias)
    lines.append('M 1 up,down')
    sets[1] = ['up', 'down']
    query(alias)
    lines.append('H')
    query(add('open'))
    query(a, math=True)
    for _ in range(60):
        lo = rng.randrange(-100, 100)
        hi = lo + rng.randrange(-2, 20)
        query(integer(lo, hi, [rng.randrange(lo - 2, lo + 22) for _ in range(8)]))
    for _ in range(100):
        # Keep generated unions shallow; include an open member to check that
        # a failing child contributes none of its own partial keys.
        children = [rng.randrange(3, 60) for _ in range(rng.randrange(6))]
        if rng.randrange(3) == 0:
            children.insert(rng.randrange(len(children) + 1), 1)
        query(union(children))
    query(integer(0, 4096))
    query(integer(0, 4097))
    query(integer(0, 4100, [1]))  # first run retained when a later run is too wide
    query(union([words, union([a, 1]), b]))  # failing child's prefix is discarded
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_keys_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_keys_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_tokens', 'checker_types', 'refinement_types', 'refine_predicates', 'refine_queries', 'intervals', 'refine_intervals', 'refine_keys'):
            text = (ROOT / 'compiler' / f'{name}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{name}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout.splitlines() == expected.splitlines()


@pytest.mark.core_quick
def test_refine_keys_ship_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_keys.dewy\0' in binary
    assert b'/compiler/refine_keys.jo\0' not in binary
