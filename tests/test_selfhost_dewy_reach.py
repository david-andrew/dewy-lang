"""Member reach traversal preserves scope snapshots, captures, deferred names and failures."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_node_store import KINDS

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/dewy_reach_jo.jo'


def corpus():
    rng = random.Random(714)
    lines = []
    for round in range(240):
        lines += ['R', 'S\t1\t6', 'S\t2\t6']
        if round % 2:
            lines.append('S\t5\t0')
        if round % 5 == 0:
            lines.append('H\t2,3')
        count = 0

        def node(kind, children=None, captures=None, **fields):
            nonlocal count
            count += 1
            n = count
            lines.append(f'M\t{KINDS.index(kind)}\t{round * 10000 + n}')
            for field, value in fields.items():
                lines.append(f'F\t{n}\t{field}\t{value}')
            for op, xs in [('L', children), ('L2', captures)]:
                if xs is not None:
                    lines.append(f'{op}\t{n}\t' + ','.join(map(str, xs)))
            return n

        def ident(name=None):
            return node('ident', name=rng.randrange(1, 5) if name is None else name,
                        flags=rng.choice([0, 1, 8, 256]))

        def typ(depth):
            if not depth:
                return node('tname')
            k = rng.randrange(8)
            if k == 0:
                return node(rng.choice(['topt', 'tptr']), a=typ(depth - 1))
            if k == 1:
                return node('tmap', a=typ(depth - 1), b=typ(depth - 1))
            if k == 2:
                return node('tarray', a=typ(depth - 1), b=ident())
            if k == 3:
                return node('trefined', a=typ(depth - 1), b=ident())
            if k == 4:
                return node('trecord', [node('param', a=typ(depth - 1))])
            if k == 5:
                return node('nil')  # deliberately unsupported
            return node(rng.choice(['tname', 'tunion', 'ttuple', 'tfn']), [typ(depth - 1), typ(0)])

        def body(depth):
            return node('block', [stmt(depth), stmt(depth)] if depth else [node('exprstmt', a=ident())])

        def head(depth):
            if depth:
                return node('lhead', op=2, a=head(0), b=head(0))
            if rng.randrange(2):
                return node('lhead', [node('tuple', [ident(1), ident(2)])], op=1, a=ident(1))
            return node('lhead', op=4, a=ident(3))

        def flow(depth):
            k = rng.choice(['if_', 'for_', 'while_', 'loopx'])
            return node(k, [ident(1)] if k == 'for_' else [],
                        a=head(1) if k == 'loopx' else ident(), b=body(depth), c=body(0))

        def fn(depth):
            params = [node('param', a=typ(1), b=ident(), name=rng.choice([1, 2, 4]))]
            if rng.randrange(2):
                params += [node('param', [node('tuple', [ident(1), ident(2)])])]
            caps = [node('ident', name=1, flags=1), node('ident', name=rng.choice([1, 2, 3]), flags=rng.choice([0, 1]))]
            generic = rng.randrange(2)
            return node('lambda', params, [] if generic else caps, a=typ(0), b=body(depth),
                        d=node('block', caps) if generic else 0, flags=64 if generic else 0)

        def expr(depth):
            if not depth:
                return ident() if rng.random() < .8 else node(rng.choice(['int_lit', 'float_lit', 'bool_lit', 'none_lit', 'hole', 'null_lit']))
            k = rng.randrange(12)
            if k == 0:
                return node('str_lit', [node('str_lit'), node('pair', a=expr(depth - 1))])
            if k == 1:
                return node(rng.choice(['field', 'not_', 'unary', 'propagate', 'namedarg']), a=expr(depth - 1))
            if k == 2:
                return node(rng.choice(['call', 'index']), [expr(depth - 1)], a=ident())
            if k == 3:
                return node(rng.choice(['binary', 'and_', 'or_', 'pair', 'coalesce']), a=expr(depth - 1), b=expr(depth - 1), c=typ(1))
            if k == 4:
                return node(rng.choice(['cast', 'istype']), a=expr(depth - 1), b=typ(1))
            if k == 5:
                return node('range', a=expr(depth - 1), b=expr(depth - 1), c=expr(depth - 1))
            if k == 6:
                return node(rng.choice(['array', 'map_lit', 'record_lit']), [expr(depth - 1), expr(depth - 1)])
            if k == 7:
                return fn(depth - 1)
            if k == 8:
                return body(depth - 1)
            if k == 9:
                return flow(depth - 1)
            if k == 10:
                pattern = node(rng.choice(['plit', 'pwild', 'pshape', 'pseq']), a=ident(), name=1)
                return node('match_', [node('arm', [pattern], b=body(depth - 1))], a=ident())
            return node('typeapply', [typ(1)], a=ident(), c=typ(1))

        def stmt(depth):
            if not depth:
                return node('exprstmt', a=ident())
            k = rng.randrange(7)
            if k == 0:
                return node(rng.choice(['vardecl', 'const_']), a=typ(1), b=expr(depth - 1), name=1, aux2=rng.choice([0, 1]))
            if k == 1:
                return node('vardecl', [node('tuple', [ident(1), ident(2)])], a=typ(1), b=expr(depth - 1))
            if k == 2:
                return node('vardecl', b=fn(depth - 1), name=1)
            if k == 3:
                return node('assign', a=ident(), b=expr(depth - 1))
            if k == 4:
                return node(rng.choice(['exprstmt', 'return_']), a=expr(depth - 1))
            if k == 5:
                return node(rng.choice(['break_', 'continue_', 'defer_']))
            return flow(depth - 1)

        mode = round % 4
        n = [lambda: expr(3), lambda: typ(3), lambda: stmt(3), lambda: head(2)][mode]()
        lines += [f'{["V", "T", "Q", "E"][mode]}\t{n}', 'D']
    return '\n'.join(lines) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_dewy_reach_match_jo(compiler, tmp_path, release):
    steps = tmp_path / 'steps'
    steps.write_text(corpus())
    outputs = []
    for module in ('dewy_reach.dewy', 'dewy_reach.jo'):
        source = tmp_path / f'{module.replace(".", "-")}.jo'
        source.write_text(DRIVER.read_text().replace("use '../../../compiler/dewy_reach.jo'",
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
    assert lines.count('state 111 222 333') == 240
    assert lines.count('reach true') > 40 and lines.count('reach false') > 20
    cached = [line.split()[1:] for line in lines if line.startswith('intern-cache ')]
    assert len(cached) == 240
    assert set(map(tuple, cached)) == {('0', '0'), ('5', '1')}
    assert 'used 6' in lines
    assert any(line.startswith('captures ') for line in lines)
    assert any(line.startswith('waiting [') and line != 'waiting [] [] []' for line in lines)


@pytest.mark.core_quick
def test_selfhost_dewy_reach_ships_dewy(compiler):
    binary = compiler.read_bytes()
    assert b'/compiler/dewy_reach.dewy\0' in binary
    assert b'/compiler/dewy_reach.jo\0' not in binary
