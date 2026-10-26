"""Differential resolver outputs, first errors, budgets and reentrant host calls."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('refine_resolve', 'refine_resolve_host', 'checker_state', 'checker_types',
           'checker_tokens', 'refinement_types', 'node_store', 'refine_queries', 'refine_predicates')
ERRORS = {
    1: 'a refinement offset needs a signed integer representation',
    2: 'a refinement offset needs a signed integer representation',
    3: 'refinement offset is too large',
    4: 'unsupported refinement offset',
    5: 'unsupported refinement offset',
    6: 'unsupported refinement offset',
    7: 'unsupported refinement term; only a constant may be added to a bound',
    8: 'refinement projection requires a value',
    9: 'refinement projection requires a value',
    10: 'unsupported refinement term; expected a scalar binding or integer bound',
    11: 'unsupported refinement predicate; expected an integer comparison',
    12: 'unsupported refinement predicate; expected an integer comparison',
    13: 'refinement comparison chain must have one direction',
    14: 'refinement range needs literal bounds',
    15: 'refinement predicate budget exhausted',
    16: 'refinement predicate budget exhausted',
    17: 'refinement predicate budget exhausted',
    18: 'unknown value',
}


def success():
    def t(kind=0, value=0, unsigned=False, path='[]', offset=0):
        return f'{kind} {value} {str(unsigned).lower()} {path} {offset}'
    x, zero, five = t(), t(1, 0), t(1, 5)
    out = [x, t(5), t(2), 'V 5', t(3, 77), 'V 6', 'N 2 0 [-1]', t(1, 11),
           t(1, -1, True), t(offset=-5), t(2, offset=5), t(1, 4294967296), t(1, -4294967296),
           'T 1 3', t(path='[3]'), 'T 1 3', t(path='[3, -1]'),
           'T 7 9', t(1, 9223372036854775807), 'T 10 8', t(4, 91),
           t(path='[-1]'), t(path='[-1]')]
    def atoms(*entries):
        out.append(f'A {len(entries)}')
        for op, a, b in entries:
            out.extend([f'O {op}', a, b])
    atoms((71, zero, x))
    atoms((72, x, five), (72, five, x))
    atoms((72, five, x))
    atoms((72, zero, x), (70, x, five))
    atoms((71, zero, x), (72, x, five))
    atoms((71, x, five), (72, zero, x))
    for low, high in [(72, 71), (72, 72), (71, 71), (71, 72)]:
        atoms((low, zero, x), (high, x, five))
    out += ['V 6', 'N 2 0 [-1]']
    atoms((71, x, t(2, offset=4)))
    out += ['S [3] [4] 1 1']
    return '\n'.join(out) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_resolve_twins(compiler, tmp_path, release):  # noqa: F811
    driver = (ROOT / 'tests/fixtures/selfhost/refine_resolve_jo.jo').read_text()
    runs = []
    for extension in ('dewy', 'jo'):
        for module in MODULES:
            text = (ROOT / 'compiler' / f'{module}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{module}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(driver.replace('../../../compiler/', '').replace(".jo'", f".{extension}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        results = []
        for mode in [0, *ERRORS]:
            ran = subprocess.run([binary, str(mode)], capture_output=True, text=True, timeout=10)
            results.append((ran.returncode, ran.stdout, ran.stderr))
            assert ran.returncode == (7 if mode else 0), ran.stdout + ran.stderr
            if mode:
                assert ran.stdout.splitlines()[-1] == f'E 700 {ERRORS[mode]}'
            else:
                assert ran.stdout == success()
        runs.append(results)
    assert runs[0] == runs[1]


@pytest.mark.core_quick
def test_resolver_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/refine_resolve.dewy\0' in binary
    assert b'/compiler/refine_resolve.jo\0' not in binary
