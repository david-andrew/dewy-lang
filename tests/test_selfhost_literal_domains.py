"""Literal-domain extraction from generated trees, including partial failures."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MIN, MAX = -(1 << 63), (1 << 63) - 1


def corpus():
    rng = random.Random(3338)
    nodes = [dict(kind=0)]
    steps, expected = [], []

    def node(kind, a=0, b=0, c=0, aux=0, value=0, name=0, flags=0, op=77, kids=()):
        nodes.append(dict(kind=kind, a=a, b=b, c=c, aux=aux, value=value, name=name, flags=flags, op=op, kids=kids))
        steps.append('N ' + ' '.join(map(str, [kind, a, b, c, aux, value, name, flags, op, *kids])))
        return len(nodes) - 1

    def leaf(n):
        if not n:
            return 0
        nd = nodes[n]
        if nd['kind'] in (3, 4):
            return leaf(nd['a'])
        if nd['kind'] == 5 and len(nd['kids']) == 1 and not nd['flags'] & 67108864:
            return leaf(nd['kids'][0])
        return n

    def values(n, text, depth, out):
        n = leaf(n)
        if not n:
            return False
        nd = nodes[n]
        if text and nd['kind'] == 2 and nd['aux'] != 1:
            out.append(nd['name'])
            return True
        if not text:
            if nd['kind'] == 1:
                out.append(nd['value'])
                return True
            if nd['kind'] == 6 and nd['op'] == 77:
                operand = nodes[leaf(nd['a'])]
                if operand['kind'] == 1 and operand['value'] != MIN:
                    out.append(-operand['value'])
                    return True
        if nd['kind'] == 7 and nd['c'] and depth < 8:
            return values(nd['b'], text, depth + 1, out) and values(nd['c'], text, depth + 1, out)
        return False

    def query(n, text, depth=0):
        steps.append(f'Q {n} {int(text)} {depth}')
        out = [-777]
        known = values(n, text, depth, out)
        expected.append(f'{leaf(n)} {str(known).lower()} {out}')

    for v in (MIN, MIN + 1, -1, 0, 1, MAX):
        n = node(1, value=v, flags=2097152)
        unary = node(6, a=n)
        query(unary, False)
    one = node(1, value=1)
    unknown = node(8)
    query(node(7, b=one, c=unknown), False)
    query(node(7, b=unknown, c=one), False)
    chain = one
    for _ in range(10):
        chain = node(7, b=chain, c=one)
        query(chain, False)
    for _ in range(2500):
        n = len(nodes)
        latest = node(rng.randrange(9), a=rng.randrange(n), b=rng.randrange(n), c=rng.randrange(n),
                      aux=rng.randrange(3), value=rng.choice([MIN, MAX, rng.randrange(-100, 101)]),
                      name=rng.randrange(-1, 100), flags=rng.choice([0, 67108864, 2097152]),
                      op=rng.choice([77, 99]), kids=tuple(rng.randrange(n) for _ in range(rng.randrange(3))))
        query(latest, False, rng.choice([0, 7, 8]))
        query(latest, True)
    for n in range(len(nodes) - 1, -1, -13):
        query(n, False)
        query(n, True)
    return '\n'.join(steps) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_literal_domains_twin_and_oracle(compiler, tmp_path, release):  # noqa: F811
    steps, expected = corpus()
    (tmp_path / 'steps').write_text(steps)
    driver = (ROOT / 'tests/fixtures/selfhost/literal_domains_jo.jo').read_text()
    for module in ('literal_domains.dewy', 'literal_domains.jo'):
        source, binary = tmp_path / f'{module}.jo', tmp_path / f'{module}.bin'
        source.write_text(driver.replace('../../../compiler/node_store.dewy', str(ROOT / 'compiler/node_store.dewy'))
                         .replace('../../../compiler/literal_domains.jo', str(ROOT / 'compiler' / module)))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, tmp_path / 'steps'], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_literal_domains_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/literal_domains.dewy\0' in binary
    assert b'/compiler/literal_domains.jo\0' not in binary
