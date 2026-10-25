"""compiler/dewy_syntax.dewy's node constructors (dewy_fast.jo's dn_node, dn_op_node and
dn_operator: a node, a node applying an operator, and `left op right`) and their frozen twin in
compiler/dewy_syntax.jo build the same tree. One Sloppy driver runs over either module, in default
and release builds, on random build sequences after the parser's two sentinels; the oracle
builds the tree by the rules: an inverted comparison applies its scalar operator over the
inverted sentinel, a binary node keeps its sentinel and operands inline, any other operator node
lists them, and an operator node starts where its left operand does."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/syntax_nodes_jo.jo'
TWIN = "use '../../../compiler/dewy_syntax.jo'"
ENUMS = dewy_enumerations((ROOT / 'compiler/dewy_tokens.dewy').read_text())
KINDS, TOKENS = ENUMS['DewyKind'], ENUMS['DewyToken']
UNINVERT = {'not_eq': 'eq', 'not_lt': 'lt', 'not_gt': 'gt', 'not_le': 'le', 'not_ge': 'ge',
            'not_contains': 'contains'}
TEXTS = ['', 'x', '()', '{}:', 'MultiplyJuxtapose', 'é', 'a b']


def sequence(rng):
    """the driver's lines, and the oracle's nodes: (kind, symbol, text, pos, name, mode, left, right, children)"""
    tree = [(KINDS.index('unknown'), 0, '', 0, 0, 0, 0, 0, []), (KINDS.index('inverted_comparison'), 0, '', 0, 0, 0, 0, 0, [])]
    lines, ids = [], []
    for _ in range(rng.randrange(1, 60)):
        kind = rng.randrange(len(KINDS))
        children = [rng.randrange(len(tree)) for _ in range(rng.choice([0, 0, 1, 2, 3, 5]))]
        pos = (rng.randrange(4) << 40) | rng.randrange(1 << 20)
        what = rng.choice('NOBBB')
        if what == 'N':
            text, name = rng.choice(TEXTS), rng.choice([0, 0, rng.randrange(1, 1 << 31)])
            lines.append(f'N\t{kind}\t{text}\t{pos}\t{",".join(map(str, children))}\t{name}')
            tree.append((kind, 0, text, pos, name, 0, 0, 0, children))
        elif what == 'O':
            symbol = rng.randrange(len(TOKENS))
            lines.append(f'O\t{kind}\t{symbol}\t{pos}\t{",".join(map(str, children))}')
            tree.append((kind, symbol, '', pos, 0, 0, 0, 0, children))
        else:
            if rng.random() < 0.5:
                kind = KINDS.index('binary')
            op = rng.choice(TOKENS + list(UNINVERT) * 8)
            left, right = rng.randrange(len(tree)), rng.randrange(len(tree))
            lines.append(f'B\t{kind}\t{TOKENS.index(op)}\t{left}\t{right}')
            scalar = UNINVERT.get(op, op)
            sentinel = 1 if scalar != op else 0
            at = tree[left][3]
            if kind == KINDS.index('binary'):
                tree.append((kind, TOKENS.index(scalar), '', at, 0, sentinel + 1, left, right, []))
            else:
                tree.append((kind, TOKENS.index(scalar), '', at, 0, 0, 0, 0, [sentinel, left, right]))
        ids.append(len(tree) - 1)
    shown = [f'{i}' for i in ids] + ['\t'.join(map(str, n[:8])) + '\t' + ','.join(map(str, n[8])) for n in tree]
    return lines, shown


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_syntax_nodes_match_jo(compiler, tmp_path, release):
    rng = random.Random(20261024)
    rounds = [sequence(rng) for _ in range(120)]
    driver = DRIVER.read_text()
    assert TWIN in driver
    binaries = []
    for module in ('dewy_syntax.jo', 'dewy_syntax.dewy'):
        source = tmp_path / f'syntax_nodes_{module.replace(".", "_")}.jo'
        source.write_text(driver.replace(TWIN, f"use '{ROOT / 'compiler' / module}'")
                          .replace("use '../../../", f"use '{ROOT}/"))
        binary = tmp_path / source.stem
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=180)
        assert built.returncode == 0, built.stdout + built.stderr
        binaries.append((module, binary))
    for k, (lines, want) in enumerate(rounds):
        data = tmp_path / f'round{k}'
        data.write_text('\n'.join(lines) + '\n')
        for module, binary in binaries:
            ran = subprocess.run([binary, data], capture_output=True, text=True, timeout=60)
            assert ran.returncode == 0, ran.stderr
            assert ran.stdout.splitlines() == want, (module, k)
