"""Borrowed type traversal preserves inference identity and structural comparisons."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
KINDS = dewy_enumerations((ROOT / 'compiler/checker_types.dewy').read_text())['TK']


def corpus():
    rng = random.Random(3620)
    lines, expected = [], []
    types = [dict(kind='void_', bits=0, flags=0, elem=0, ref=0, st=0, args=[])]
    structs = [(0, [])]

    def record(decl, args):
        structs.append((decl, list(args)))
        lines.append(f'S {decl} {",".join(map(str, args)) or "-"}')
        return len(structs) - 1

    def add(kind, bits=0, flags=0, elem=0, ref=0, st=0, args=(), sign=0, mask=0):
        types.append(dict(kind=kind, bits=bits, flags=flags, elem=elem, ref=ref, st=st, args=list(args)))
        lines.append(f'T {KINDS.index(kind)} {bits} {flags} {elem} {ref} {st} {",".join(map(str, args)) or "-"} {sign} {mask}')
        return len(types) - 1

    def prune(t):
        while t and types[t]['kind'] == 'var' and types[t]['ref']:
            t = types[t]['ref']
        return t

    def equal(a, b):
        a, b = prune(a), prune(b)
        if a == b:
            return True
        x, y = types[a], types[b]
        if not a or not b or not ((x['flags'] | y['flags']) & 1):
            return False
        if (x['kind'], len(x['args']), x['bits']) != (y['kind'], len(y['args']), y['bits']) or x['kind'] == 'var':
            return False
        if x['kind'] in ('struct_', 'enum_'):
            if x['st'] == y['st']:
                return True
            dx, ax = structs[x['st']]
            dy, ay = structs[y['st']]
            return dx == dy and len(ax) == len(ay) and all(equal(i, j) for i, j in zip(ax, ay))
        return x['st'] == y['st'] and equal(x['elem'], y['elem']) and all(equal(i, j) for i, j in zip(x['args'], y['args']))

    def occurs(v, t):
        t = prune(t)
        if v == t:
            return True
        x = types[t]
        if not x['flags'] & 1:
            return False
        children = ([x['elem']] if x['elem'] else []) + x['args']
        if x['kind'] in ('struct_', 'enum_') and x['st']:
            children = children + structs[x['st']][1]
        return any(occurs(v, c) for c in children)

    def query(a, b, v):
        lines.append(f'Q {a} {b} {v}')
        expected.append(f'{str(equal(a, b)).lower()} {str(occurs(v, a)).lower()}')

    scalar = add('int_', bits=64)
    variable = add('var', flags=1)
    other = add('var', flags=1)
    alias = add('var', flags=1, ref=variable)
    for kind in KINDS:
        if kind == 'var':
            continue
        st = record(1, [variable, scalar]) if kind in ('struct_', 'enum_') else 1
        twin_st = record(1, [alias, scalar]) if kind in ('struct_', 'enum_') else 1
        a = add(kind, flags=1, elem=variable, args=[variable, scalar], st=st)
        b = add(kind, flags=1, elem=alias, args=[alias, scalar], st=twin_st, sign=1, mask=7)
        c = add(kind, flags=1, elem=other, args=[other, scalar], st=st)
        d = add(kind, flags=0, elem=variable, args=[variable, scalar], st=st)
        for left in (a, b, c, d):
            for right in (0, a, b, c, d, variable, alias):
                for v in (0, variable, alias, scalar, other, left):
                    query(left, right, v)
    # Occurs' struct metadata zero is deliberately not traversed; equality's
    # matching struct IDs succeeds even when ordinary argument contents differ.
    a = add('struct_', flags=1, st=0)
    query(a, a, variable)
    # Observe an inference binding after earlier queries; do not cache results.
    held = add('array', flags=1, elem=variable)
    target = add('array', flags=1, elem=other)
    query(held, target, variable)
    lines.append(f'R {variable} {other}')
    types[variable]['ref'] = other
    query(held, target, variable)
    query(held, target, other)
    # A deep, shared DAG stays a query over selected occurrences, no copied arenas.
    deep = other
    for _ in range(48):
        deep = add('array', flags=1, elem=deep)
    query(deep, held, other)
    query(deep, deep, scalar)
    for _ in range(240):
        kind = rng.choice(KINDS)
        n = len(types)
        children = [rng.randrange(n) for _ in range(rng.randrange(4))]
        st = record(rng.randrange(4), children) if kind in ('struct_', 'enum_') else rng.randrange(4)
        a = add(kind, bits=rng.choice([0, 8, 32, 64]), flags=rng.randrange(4),
                elem=rng.randrange(n), ref=rng.randrange(n) if kind == 'var' else 0,
                st=st, args=children)
        clone = types[a].copy()
        if kind != 'var':
            b = add(**clone, sign=1, mask=15)
            query(a, b, rng.randrange(n))
    for _ in range(2500):
        query(rng.randrange(len(types)), rng.randrange(len(types)), rng.randrange(len(types)))
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_query_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/type_queries_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_tokens', 'checker_types', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries'):
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
def test_type_queries_ship_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/type_queries.dewy\0' in binary
    assert b'/compiler/type_queries.jo\0' not in binary
