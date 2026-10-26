"""Predicate canonicalization/interner and interval queries against an independent model."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
TOK = dewy_enumerations((ROOT / 'compiler/checker_tokens.dewy').read_text())['Tok']
MIN, MAX = -(1 << 63), (1 << 63) - 1
ENDS = [MIN, MIN + 1, -100, -1, 0, 1, 100, MAX - 1, MAX]


def wrap(x):
    return (x - MIN) % (1 << 64) + MIN


def boolean(x):
    return str(bool(x)).lower()


def term_text(t):
    k, u, v, off, path = t
    return f'{k},{v},{boolean(u)},{off},{list(path)}'


def atom_text(a):
    x, y, op = a
    return f'{op}:{term_text(x)}:{term_text(y)}'


def row_text(row):
    return ';'.join(map(atom_text, row))


def normalized(a):
    x, y, op = a
    offset = wrap(y[3] - x[3])
    x = (*x[:3], 0, x[4])
    y = (y[0], y[1], wrap(y[2] + offset) if y[0] == 1 else y[2],
         0 if y[0] == 1 else offset, y[4])
    return x, y, op


def expand(a):
    x, y, op = a
    name = TOK[op]
    if name in ('gt', 'ge'):
        x, y, op = y, x, TOK.index('lt' if name == 'gt' else 'le')
    if name == 'eq':
        return [normalized((x, y, TOK.index('le'))), normalized((y, x, TOK.index('le')))]
    if name == 'ne' and y < x:
        x, y = y, x
    return [normalized((x, y, op))]


def interval(row, lo, hi):
    for x, y, op in row:
        if TOK[op] not in ('le', 'lt') or x[1] or y[1]:
            continue
        if x[0] == 0 and not x[4] and y[0] == 1:
            if TOK[op] == 'le':
                hi = min(hi, y[2])
            elif y[2] != MIN:
                hi = min(hi, y[2] - 1)
        elif x[0] == 1 and y[0] == 0 and not y[4] and MIN <= x[2] + wrap(-y[3]) <= MAX:
            c = wrap(x[2] - y[3])
            if TOK[op] == 'le':
                lo = max(lo, c)
            elif c != MAX:
                lo = max(lo, c + 1)
    return lo, hi


def corpus():
    rng = random.Random(3509)
    terms = [(0, False, 0, 0, ()), (0, False, 0, 0, (-1,))]
    terms += [(kind, unsigned, v, offset, path)
              for kind in range(6) for unsigned in (False, True)
              for v in ENDS for offset in (0, MIN, MAX) for path in ((), (-1,), (4, -1))]
    for _ in range(300):
        terms.append((rng.randrange(6), rng.choice([False, True]), rng.choice(ENDS),
                      rng.choice(ENDS), tuple(rng.randrange(-1, 9) for _ in range(rng.randrange(8)))))
    lines = [f'T {k} {v} {int(u)} {off} {",".join(map(str, path)) or "-"}' for k, u, v, off, path in terms]
    atoms = []
    # Every op shares equal operands: ordering must use ordinal, not union-member text.
    for op in range(len(TOK)):
        atoms.append((terms[0], terms[1], op))
        lines.append(f'A {op} 0 1')
    for _ in range(1800):
        i, j = rng.randrange(len(terms)), rng.randrange(len(terms))
        if rng.random() < 0.4:
            i = rng.randrange(2)
        elif rng.random() < 0.5:
            j = rng.randrange(2)
        op = TOK.index(rng.choice(['eq', 'ne', 'lt', 'le', 'gt', 'ge']))
        atoms.append((terms[i], terms[j], op))
        lines.append(f'A {op} {i} {j}')
    expected = []
    for op in range(len(TOK)):
        lines.append(f'K {op}')
        expected.append(str(op))
        for other in range(len(TOK)):
            lines.append(f'C 0 1 {op} {other}')
            expected.append(f'{boolean(terms[0] < terms[1])} {boolean(op < other)}')
    for i, a in enumerate(atoms):
        lines.append(f'N {i}')
        expected.append(f'{atom_text(normalized(a))}|{row_text(expand(a))}|{atom_text(a)}')
    table = [None]  # predicate 0 is a sentinel, even an empty row interns at 1
    for step in range(800):
        if step % 40 == 0:
            lines.append('R')
            table = [None]
        ids = [rng.randrange(len(atoms)) for _ in range(rng.randrange(12))]
        if step % 10 == 0:
            ids += ids
        row = [atoms[i] for i in ids]
        canonical = sorted(set(row))
        if canonical not in table:
            table.append(canonical)
        key = table.index(canonical)
        for selection in (ids, list(reversed(ids))):
            given = [atoms[i] for i in selection]
            lines.append('I ' + (','.join(map(str, selection)) or '-'))
            expected.append(f'{key}|{row_text(canonical)}|{row_text(given)}')
        lo, hi = sorted(rng.choices(ENDS, k=2))
        nz, reason, witness, wide = rng.randrange(2), rng.randrange(8), rng.choice(ENDS), rng.randrange(2)
        lines.append(f'Q {",".join(map(str, ids)) or "-"} {lo} {hi} {nz} {reason} {witness} {wide}')
        low, high = interval(row, lo, hi)
        length_only = all(t[0] == 1 or t[4] and t[4][-1] == -1 for a in row for t in a[:2])
        kinds = [any(t[0] == k for a in row for t in a[:2]) for k in (2, 5)]
        expected.append(f'{low} {high} {boolean(nz)} {reason} {witness} {boolean(wide)}|'
                        + ' '.join(map(boolean, [length_only, *kinds])))
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_predicates_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_predicates_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_tokens', 'refinement_types', 'refine_predicates'):
            text = (ROOT / 'compiler' / f'{name}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{name}.{extension}').write_text(text)
        source = tmp_path / 'driver.jo'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        binary = tmp_path / 'driver'
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout.splitlines() == expected.splitlines()


@pytest.mark.core_quick
def test_refine_predicates_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_predicates.dewy\0' in binary
    assert b'/compiler/refine_predicates.jo\0' not in binary
