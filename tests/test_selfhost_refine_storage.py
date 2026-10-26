"""Storage walks: independent graph oracle, exact callback trace and reentry."""
import random
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    rng = random.Random(4012)
    steps, expected = [], []
    types, structs = [(0, 0, 0, 0, [])], [None]
    resolved, calls = set(), []

    def ty(kind=2, elem=0, st=0, ref=0, args=()):
        types.append((kind, elem, st, ref, args))
        steps.append(' '.join(map(str, ('T', kind, elem, st, ref, *args))))
        return len(types) - 1

    def record(members, ready=False, nested=0):
        si = len(structs)
        structs.append((members, nested))
        steps.append(' '.join(map(str, ('S', int(ready), nested, *members))))
        if ready:
            resolved.add(si)
        return si

    def visit(t, seen):
        while t and types[t][0] == 12 and types[t][3]:
            t = types[t][3]
        if t in seen:
            return False
        if len(seen) >= 32:
            return True
        kind, elem, si, _, args = types[t]
        if kind == 26:
            return True
        if kind not in (5, 8, 10, 11, 21):
            return False
        if kind == 8:
            if si not in resolved:
                resolved.add(si)
                calls.append(si)
                if structs[si][1]:
                    found = visit(structs[si][1], [])
                    expected.append(f'N {si} {str(found).lower()}')
            children = structs[si][0]
        elif kind == 10:
            children = args
        else:
            children = [elem]
        return any(visit(c, seen + [t]) for c in children)

    scalar = ty()
    refined = ty(26, scalar)
    fn = ty(7, refined, args=[refined])  # callable contracts are values
    for kind in (5, 11, 21):
        ty(kind, refined)
    ty(10, args=[scalar, fn, refined])
    ty(12, ref=refined)
    ty(12)  # unbound inference
    ty(10, args=[])
    # Cycles before depth limits, and scalar vs cycle exactly at depth 32.
    cycle = len(types)
    for i in range(32):
        ty(5, cycle if i == 31 else len(types) + 1)
    deep = scalar
    for _ in range(33):
        deep = ty(5, deep)
    # A diamond must reuse neither an ancestor stack nor a resolution callback.
    leaf_si = record([scalar], ready=True)
    leaf = ty(8, st=leaf_si)
    ty(10, args=[leaf, leaf, refined])
    lazy_si = record([refined])
    lazy = ty(8, st=lazy_si)
    outer = ty(5, lazy)
    structs[lazy_si] = ([refined], outer)
    # Adjust the declaration to request a fresh walk of an active ancestor.
    steps[next(i for i, s in enumerate(steps) if s == f'S 0 0 {refined}')] = f'S 0 {outer} {refined}'
    empty = ty(8, st=record([]))
    for _ in range(180):
        kind = rng.choice([2, 5, 7, 8, 10, 11, 12, 21, 26])
        if kind == 8:
            ty(kind, st=record([rng.randrange(1, len(types)) for _ in range(rng.randrange(5))], rng.choice([True, False])))
        else:
            ty(kind, rng.randrange(1, len(types)), ref=rng.randrange(1, len(types)) if kind == 12 else 0,
               args=[rng.randrange(1, len(types)) for _ in range(rng.randrange(5))] if kind in (7, 10) else [])
    queries = [outer, outer, empty, cycle, deep, *range(1, len(types))]
    for t in queries:
        steps.append(f'Q {t}')
        found = visit(t, [])
        expected.append(f'Q {t} {str(found).lower()}')
        expected.extend(f'C {si}' for si in calls)
        calls.clear()
    return '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_storage_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_storage_jo.jo').read_text()
    modules = ('checker_tokens', 'checker_services', 'checker_types', 'refine_queries', 'refinement_types', 'refine_predicates', 'refine_storage')
    for extension in ('dewy', 'jo'):
        for name in modules:
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
def test_storage_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_storage.dewy\0' in binary
    assert b'/compiler/refine_storage.jo\0' not in binary
