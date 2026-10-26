"""Demanded string-write joins and captures against a list-based history model."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    rng = random.Random(3318)
    steps, expected = [], []
    states, captures = {}, {}

    def values(binding):
        own = states[binding][:]
        if own and binding in captures:
            inherited = values(captures[binding])
            return own + inherited if inherited else []
        return own

    def step(op, binding=None, *args):
        steps.append(' '.join(map(str, [op, *([] if binding is None else [binding]), *args])))
        if op == 'R':
            states.clear()
            captures.clear()
        elif op == 'D':
            states[binding] = list(args)
        elif op == 'W':
            if states.get(binding):
                states[binding] = states[binding] + list(args[1:]) if args[0] else []
        elif op == 'C':
            if args[0] in states:
                states[binding] = states[args[0]][:]
                captures[binding] = args[0]
        else:
            expected.append(str(values(binding)) if binding in states else 'absent')

    step('R')
    step('W', 1, 1, 42)
    step('C', 2, 1)
    step('Q', 2)
    step('D', -1, 7, 7)
    step('C', 1, -1)
    step('C', 2, 1)
    step('W', -1, 1, 8)
    for b in (2, 1, -1, 2):
        step('Q', b)
    step('W', -1, 0, 99)
    step('W', -1, 1, 10)
    step('Q', 2)
    for _ in range(120):
        step('R')
        for b in range(1, 41):
            if b > 1 and rng.random() < .55:
                step('C', b, rng.randrange(1, b))
            else:
                step('D', b, *[rng.randrange(20) for _ in range(rng.randrange(5))])
            for _ in range(rng.randrange(5)):
                target = rng.randrange(1, b + 1)
                step('W', target, int(rng.random() < .9), *[rng.randrange(20) for _ in range(rng.randrange(5))])
            step('Q', b)
        for b in [*range(40, 0, -1), *range(1, 41)]:
            step('Q', b)
    return '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_text_domains_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/text_domains_jo.jo').read_text()
    for module in ('text_domains.dewy', 'text_domains.jo'):
        source, binary = tmp_path / f'{module}.jo', tmp_path / f'{module}.bin'
        source.write_text(driver.replace('../../../compiler/text_domains.jo', str(ROOT / 'compiler' / module)))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_text_domains_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/text_domains.dewy\0' in binary
    assert b'/compiler/text_domains.jo\0' not in binary
