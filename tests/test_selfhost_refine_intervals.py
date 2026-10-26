"""Refinement domains agree with symbolic integer constraints and the frozen twin."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
KINDS = dewy_enumerations((ROOT / 'compiler/checker_types.dewy').read_text())['TK']
TOKENS = dewy_enumerations((ROOT / 'compiler/checker_tokens.dewy').read_text())['Tok']
MIN, MAX = -(1 << 63), (1 << 63) - 1


def word(n):
    return (n - MIN) % (1 << 64) + MIN


def corpus():
    rng = random.Random(3610)
    lines, expected = [], []

    def case(bits, sign, atoms=(), kind='int_', math=False):
        lines.append(f'T {KINDS.index(kind)} {bits} {int(sign)}')
        for op, a, b in atoms:
            lines.append(f'A {TOKENS.index(op)} ' + ' '.join(map(str, (*a[:4], *b[:4], a[4], b[4]))))
        # Reuse the same arenas across cases; both direct and inferred references
        # must see new type fields and predicate rows immediately.
        for t in (1, 2, 4):
            lines.append(f'Q {t} {1 if math else 0}')
            known = kind == 'int_' and not math
            low, high = [], []
            constraints = atoms if t != 1 else ()
            lo = -(1 << (bits - 1)) if sign else 0
            hi = (1 << (bits - int(sign))) - 1
            excluded = set()
            for op, a, b in constraints if known else ():
                if a[4] or b[4] or op not in ('lt', 'le', 'ne') or (a[0], b[0]) not in ((1, 0), (0, 1)):
                    known = False
                    break
                left_literal = a[0] == 1
                literal = a if left_literal else b
                v = literal[1]
                if left_literal and b[3]:
                    negative = word(-b[3])
                    if a[2] or not MIN <= v + negative <= MAX:
                        known = False
                        break
                    v = word(v - b[3])
                if literal[2] and v < 0:
                    v += 1 << 64
                if op == 'ne':
                    excluded.add(v)
                elif left_literal:
                    lo = max(lo, v + (op == 'lt'))
                else:
                    hi = min(hi, v - (op == 'lt'))
            if known:
                # Independently split the mathematical domain at excluded points
                # and at the signed-word boundary; encode only at the very end.
                for start, stop, out in ((lo, min(hi, MAX), low), (max(lo, MAX + 1), hi, high)):
                    if start > stop:
                        continue
                    cursor = start
                    for value in sorted(excluded):
                        if cursor <= value <= stop:
                            if cursor < value:
                                out.extend((word(cursor), word(value - 1)))
                            cursor = value + 1
                    if cursor <= stop:
                        out.extend((word(cursor), word(stop)))
            narrow = known and not high
            fmt = lambda xs: '[' + ', '.join(map(str, xs)) + ']'
            expected.append(f'{str(known).lower()} {fmt(low)} {fmt(high)} {str(narrow).lower()} {fmt(low if narrow else [])}')

    def term(kind=0, value=0, unsigned=0, offset=0, path=0):
        return kind, value, unsigned, offset, path

    for bits in (8, 16, 32, 64):
        for sign in (False, True):
            case(bits, sign)
            end = (1 << (bits - int(sign))) - 1
            start = -(1 << (bits - 1)) if sign else 0
            values = sorted({start, end, 0, 1, min(end, MAX), max(start, -1)})
            if not sign and bits == 64:
                values += [1 << 63, (1 << 63) + 1]
            for value in values:
                lit = term(1, word(value), int(value > MAX))
                for op in ('lt', 'le', 'ne'):
                    case(bits, sign, [(op, term(), lit)])
                    case(bits, sign, [(op, lit, term())])
            for _ in range(80):
                atoms = []
                for _ in range(rng.randrange(10)):
                    value = rng.choice(values) if rng.randrange(2) else rng.randint(start, end)
                    lit = term(1, word(value), int(value > MAX))
                    self = term()
                    if sign and rng.randrange(2):
                        self = term(offset=rng.choice([-4, -1, 0, 1, 4, MIN, MAX]))
                    a, b = (lit, self) if rng.randrange(2) else (term(), lit)
                    atoms.append((rng.choice(['lt', 'le', 'ne']), a, b))
                case(bits, sign, atoms)
    for kind in KINDS:
        if kind not in ('refined', 'var'):
            case(64, True, kind=kind)
    case(64, True, math=True)
    for bad in range(2, 6):
        case(64, True, [('le', term(bad), term(1, 10))])
    for op in ('eq', 'ge', 'gt', 'plus'):
        case(64, True, [(op, term(), term(1, 10))])
    case(64, True, [('le', term(path=1), term(1, 10))])
    case(64, True, [('le', term(1, 10), term(path=1))])
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_intervals_twins_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/refine_intervals_jo.jo').read_text()
    for extension in ('dewy', 'jo'):
        for name in ('checker_tokens', 'checker_types', 'refinement_types', 'refine_predicates', 'refine_queries', 'intervals', 'refine_intervals'):
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
def test_refine_intervals_ship_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_intervals.dewy\0' in binary
    assert b'/compiler/refine_intervals.jo\0' not in binary
