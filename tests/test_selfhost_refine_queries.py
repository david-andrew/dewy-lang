"""Read-only refinement queries over synthetic shared type graphs, including depth limits."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
KINDS = dewy_enumerations((ROOT / 'compiler/checker_types.dewy').read_text())['TK']


def corpus():
    rng = random.Random(3510)
    types = [dict(kind='void_', elem=0, ref=0, args=[], union=False, formal=0)]
    lines, expected = [], []

    def add(kind, elem=0, ref=0, args=(), union=False, formal=0):
        types.append(dict(kind=kind, elem=elem, ref=ref, args=list(args), union=union, formal=formal))
        lines.append(f'T {KINDS.index(kind)} {elem} {ref} {",".join(map(str, args)) or "-"} {int(union)} {formal}')
        return len(types) - 1

    def prune(t):
        while t and types[t]['kind'] == 'var' and types[t]['ref']:
            t = types[t]['ref']
        return t

    def contains(t, want, depth):
        t = prune(t)
        if t == want:
            return True
        if depth >= 32:
            return False
        node = types[t]
        if node['kind'] in ('refined', 'opt', 'array', 'fixed'):
            return contains(node['elem'], want, depth + 1)
        return node['kind'] == 'enum_' and node['union'] and any(contains(c, want, depth + 1) for c in node['args'])

    def nested_formals(t, nested, depth):
        if depth >= 32:
            return True
        node = types[prune(t)]
        if node['kind'] == 'refined':
            return nested and node['formal'] == 2 or nested_formals(node['elem'], nested, depth + 1)
        if node['kind'] in ('array', 'fixed', 'opt'):
            return nested_formals(node['elem'], True, depth + 1)
        return node['kind'] == 'tuple' and any(nested_formals(c, True, depth + 1) for c in node['args'])

    def query(t, want, depth, nested):
        lines.append(f'Q {t} {want} {depth} {int(nested)}')
        expected.append(f'{prune(t)} {str(contains(t, want, depth)).lower()} {str(nested_formals(t, nested, depth)).lower()}')

    scalar = add('int_')
    formal = add('refined', scalar, formal=2)
    nonformal = add('refined', scalar, formal=5)
    alias = add('var', ref=formal)
    union = add('enum_', args=[scalar, alias], union=True)
    plain_enum = add('enum_', args=[formal], union=False)
    tuple_ = add('tuple', args=[scalar, nonformal, alias])
    fn = add('fn_', elem=formal, args=[formal])
    chain = [formal]
    for i in range(35):
        chain.append(add(['array', 'fixed', 'opt'][i % 3], elem=chain[-1]))
    for t in [scalar, formal, nonformal, alias, union, plain_enum, tuple_, fn, *chain]:
        for want in (scalar, formal, alias, t):
            for depth in (0, 30, 31, 32, 33):
                for nested in (False, True):
                    query(t, want, depth, nested)
    cycle = add('array')
    lines.append(f'E {cycle} {cycle}')
    types[cycle]['elem'] = cycle
    for depth in (0, 31, 32):
        query(cycle, scalar, depth, False)
        query(cycle, cycle, depth, True)
    # Subsequent writes must be observed: no stale memoized result may survive a query.
    lines.append(f'E {cycle} {formal}')
    types[cycle]['elem'] = formal
    query(cycle, formal, 0, False)
    for _ in range(350):
        kind = rng.choice(KINDS)
        n = len(types)
        add(kind, elem=rng.randrange(n), ref=rng.randrange(n),
            args=[rng.randrange(n) for _ in range(rng.randrange(5))],
            union=rng.choice([False, True]), formal=rng.randrange(6))
    for _ in range(3500):
        query(rng.randrange(len(types)), rng.randrange(len(types)),
              rng.choice([0, 1, 28, 30, 31, 32, 33]), rng.choice([False, True]))
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_query_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_queries_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_tokens', 'checker_types', 'refinement_types', 'refine_predicates', 'refine_queries'):
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
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_refine_queries_ship_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_queries.dewy\0' in binary
    assert b'/compiler/refine_queries.jo\0' not in binary
