"""Independent parser traversals: mixed-flow positions, collection and copy recognition."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_node_store import KINDS

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_walk_jo.jo'


def corpus():
    rng = random.Random(613)
    lines = []
    for round in range(100):
        lines.append('R')
        count = 0

        def node(kind, children=None, **fields):
            nonlocal count
            count += 1
            n = count
            lines.append(f'M\t{KINDS.index(kind)}\t{round * 10000 + n}')
            for field, value in fields.items():
                lines.append(f'F\t{n}\t{field}\t{value}')
            if children is not None:
                lines.append(f'L\t{n}\t' + ','.join(map(str, children)))
            return n

        def block(depth):
            return node('block', [statement(depth)] if rng.random() < .9 else [])

        def statement(depth):
            choice = rng.randrange(9 if depth else 5)
            if choice == 0:
                return node('return_', a=node('int_lit'))
            if choice == 1:
                return node('exprstmt', a=node('pair', a=node('int_lit'), b=node('int_lit')))
            if choice == 2:
                return node('exprstmt', a=node('int_lit'))
            if choice == 3:
                return node('exprstmt', a=node('call', a=node('ident')))
            if choice == 4:
                return node('exprstmt', a=node('parallel_region'))
            if choice == 5:
                return node('exprstmt', a=block(depth - 1))
            if choice == 6:
                arms = [node('arm', b=block(depth - 1)) for _ in range(rng.randrange(4))]
                return node('exprstmt', a=node('match_', arms))
            # Include ordinary flows and flattened else-if chains at matching positions.
            flow = node(rng.choice(['if_', 'for_', 'while_', 'loopx']), b=block(depth - 1), c=block(depth - 1))
            if choice == 8:
                inner = node('if_', b=block(0), c=block(0))
                rest = node('block', [inner], pos=round * 10000 + flow)
                lines.append(f'F\t{flow}\tc\t{rest}')
            return flow

        root = statement(3)
        wrapper = node('block', [root])
        # State with an earlier position must retain it. Tag membership includes false entries.
        lines += [f'T\t{root}', f'Y\t{root}\t0', f'Y\t{root}\t9001']
        if round % 4 == 0:
            lines.append(f'G\t{wrapper}')
        lines += [f'Q\t{root}\t{round % 2}\t{(round // 2) % 2}', 'D',
                  f'B\t{wrapper}\t{round % 2}', 'D']
        lines.append('R')
        count = 0
        for name in (1, 2):
            value = node('field', a=node('ident'), name=name)
            lines.append(f'X\t{value}')
            value = node('call', a=value)
            lines.append(f'X\t{value}')
            for _ in range(5):
                value = node('block', [node('exprstmt', a=value)])
                lines.append(f'X\t{value}')
        empty = node('block', [])
        lines += [f'X\t{empty}', 'T\t0', 'T\t-1', 'Y\t0\t0', 'Q\t-1\t0\t0']
    return '\n'.join(lines) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_walk_match_jo(compiler, tmp_path, release):
    steps = tmp_path / 'steps'
    steps.write_text(corpus())
    outputs = []
    for module in ('dewy_walk.dewy', 'dewy_walk.jo'):
        source = tmp_path / f'{module.replace(".", "-")}.jo'
        source.write_text(DRIVER.read_text().replace("use '../../../compiler/dewy_walk.jo'",
                         f"use '{ROOT / 'compiler' / module}'").replace("use '../../../", f"use '{ROOT}/"))
        binary = source.with_suffix('')
        run = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                             capture_output=True, text=True, timeout=120)
        assert run.returncode == 0, run.stdout + run.stderr
        run = subprocess.run([binary, steps], capture_output=True, text=True, timeout=60)
        assert run.returncode == 0, run.stdout + run.stderr
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1]
    lines = outputs[0].splitlines()
    assert lines.count('copy true') == 700
    assert lines.count('copy false') == 800
    assert 'tail 1' in lines and 'tail 2' in lines
    assert any(line.startswith('kind 0 ') and not line.endswith(' 0') for line in lines)
    assert any(line.startswith('block false ') for line in lines)
    assert any(line.startswith('block true ') for line in lines)


@pytest.mark.core_quick
def test_selfhost_dewy_walk_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_walk.dewy\0' in binary
    assert b'/compiler/dewy_walk.jo\0' not in binary
