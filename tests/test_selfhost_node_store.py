"""compiler/node_store.dewy (the node store: the Node record and the NK kinds, a new node, a
node's lists as runs of the store's second array, a node's children, a subtree's copy): it
ships, and its frozen implementation-language twin compiler/node_store.jo gives the same
answers. One Sloppy driver runs over either module on random sequences of node building; the
oracle below keeps the store as Python lists."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_selfhost_twins import dewy_enumerations

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'tests/fixtures/selfhost/node_store_jo.jo'
KINDS = dewy_enumerations((ROOT / 'compiler/node_store.dewy').read_text())['NK']
FIELDS = ['kind', 'op', 'flags', 'pos', 'a', 'b', 'c', 'd', 'list', 'nlist', 'list2', 'nlist2',
          'name', 'sval', 'ival', 'fval', 'type', 'sym', 'aux', 'aux2', 'mod']
CHECKED = 128   # (ast.jo's NF_CHECKED: a copy is checked again)
I32 = [0, 1, 7, -1, 128, 129, 255, 2**31 - 1, -2**31, 2**31 - 128, -129]


def i32(v):
    return (v + 2**31) % 2**32 - 2**31


class Oracle:
    def __init__(self):
        self.nodes = [self.blank('nil', 0)]
        self.runs = []

    @staticmethod
    def blank(kind, pos):
        node = dict.fromkeys(FIELDS, 0)
        node.update(kind=kind, pos=pos, fval=0.0)
        return node

    def mk(self, kind, pos):
        self.nodes.append(self.blank(kind, pos))
        return len(self.nodes) - 1

    def run(self, xs):
        start = len(self.runs)
        self.runs += [i32(x) for x in xs]
        return start

    def set_list(self, n, xs, second=False):
        start = self.run(xs)
        self.nodes[n]['list2' if second else 'list'] = start
        self.nodes[n]['nlist2' if second else 'nlist'] = len(xs)

    def kids(self, n, second=False):
        start = self.nodes[n]['list2' if second else 'list']
        return self.runs[start:start + self.nodes[n]['nlist2' if second else 'nlist']]

    def clone(self, n):
        if n == 0:
            return 0
        nd = dict(self.nodes[n])
        if nd['kind'] not in ('fn_', 'struct_', 'enum_'):
            nd['sym'] = 0
        if nd['kind'] != 'conv':
            nd['type'] = 0
        nd['flags'] = i32(nd['flags'] & ~CHECKED)
        c = len(self.nodes)
        self.nodes.append(nd)
        for f in 'abcd':
            if nd[f] != 0:
                self.nodes[c][f] = self.clone(nd[f])
        for second in (False, True):
            if nd['nlist2' if second else 'nlist'] > 0:
                start = nd['list2' if second else 'list']
                xs = [self.clone(x) for x in self.runs[start:start + nd['nlist2' if second else 'nlist']]]
                self.set_list(c, xs, second)
        return c

    def size(self, n, seen=0):
        """the nodes a copy of n makes (a shared child is copied each time it is reached)"""
        if n == 0 or seen > 400:
            return seen
        nd = self.nodes[n]
        seen += 1
        for x in [nd[f] for f in 'abcd'] + self.kids(n) + self.kids(n, True):
            seen = self.size(x, seen)
        return seen

    def dump(self):
        out = []
        for i, d in enumerate(self.nodes):
            values = [d[f] for f in FIELDS]
            values[FIELDS.index('fval')] = show_float(d['fval'])
            out.append(' '.join(str(v) for v in [i] + values))
        out.append(show_list(self.runs))
        return out


def show_list(xs):
    return '[' + ', '.join(str(x) for x in xs) + ']'


def show_float(x):
    return repr(float(x))


def corpus(seed, rounds=40, steps=160):
    """lines for the driver and the answers the oracle gives"""
    rng = random.Random(seed)
    lines, want = [], []
    for _ in range(rounds):
        o = Oracle()
        lines.append('R')
        for _ in range(steps):
            n = len(o.nodes)
            # (children point back, so the store stays a graph without cycles: a copy ends)
            older = lambda: rng.randrange(1, n) if n > 1 else 0  # noqa: E731
            r = rng.random()
            if r < 0.3 or n < 3:
                k = rng.randrange(len(KINDS))
                pos = rng.choice([0, 1, rng.randrange(1 << 40)])
                lines.append(f'M\t{k}\t{pos}')
                want.append(str(o.mk(KINDS[k], pos)))
            elif r < 0.45:
                target = max(older(), older())
                xs = [rng.randrange(1, target) if target > 1 and rng.random() < 0.9 else 0
                      for _ in range(rng.choice([0, 1, 2, 3, 5, 40]))]
                second = rng.random() < 0.3
                lines.append(f'{"L2" if second else "L"}\t{target}\t{",".join(map(str, xs))}')
                o.set_list(target, xs, second)
            elif r < 0.5:
                xs = [rng.choice(I32 + [rng.randrange(-2**31, 2**31)]) for _ in range(rng.choice([0, 1, 4]))]
                lines.append(f'U\t{",".join(map(str, xs))}')
                want.append(str(o.run(xs)))
            elif r < 0.75:
                target = older()
                field = rng.choice(['kind', 'op', 'flags', 'a', 'b', 'c', 'd', 'name', 'sval', 'ival', 'fval',
                                    'type', 'sym', 'aux', 'aux2', 'mod', 'kind', 'flags', 'a', 'b'])
                if field == 'kind':
                    k = rng.choice([rng.randrange(len(KINDS)), KINDS.index('fn_'), KINDS.index('conv'),
                                    KINDS.index('struct_'), KINDS.index('enum_')])
                    lines.append(f'F\t{target}\tkind\t{k}')
                    o.nodes[target]['kind'] = KINDS[k]
                    continue
                if field in 'abcd':
                    v = rng.randrange(0, target) if target > 1 else 0
                elif field == 'ival':
                    v = rng.choice([0, -1, 2**62, rng.randrange(-2**63, 2**63)])
                elif field == 'fval':
                    v = rng.randrange(-1000, 1000)
                else:
                    v = rng.choice(I32 + [rng.randrange(-2**31, 2**31)])
                lines.append(f'F\t{target}\t{field}\t{v}')
                o.nodes[target][field] = v / 4.0 if field == 'fval' else v if field == 'ival' else i32(v)
            elif r < 0.9:
                target = rng.choice([0, older(), older()])
                second = rng.random() < 0.3
                lines.append(f'{"K2" if second else "K"}\t{target}')
                want.append(show_list(o.kids(target, second)))
            else:
                target = rng.choice([0, older()])
                if o.size(target) <= 400:
                    lines.append(f'C\t{target}')
                    want.append(str(o.clone(target)))
        lines.append('D')
        want += o.dump()
    return '\n'.join(lines) + '\n', '\n'.join(want) + '\n'


def build(compiler, source, binary, release):
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_node_store_match_jo(compiler, tmp_path, release):  # noqa: F811
    driver = DRIVER.read_text()
    twin = "use '../../../compiler/node_store.jo'"
    assert twin in driver
    text, want = corpus(16)
    steps = tmp_path / 'steps'
    steps.write_text(text)
    outputs = []
    for module in ('node_store.dewy', 'node_store.jo'):
        source = tmp_path / f'driver-{module.replace(".", "-")}.jo'
        source.write_text(driver.replace(twin, f"use '{ROOT / 'compiler' / module}'"))
        binary = build(compiler, source, tmp_path / source.stem, release)
        ran = subprocess.run([binary, steps], capture_output=True, text=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    for got, expected in zip(outputs[0].split('\n'), want.split('\n')):
        assert got == expected
    assert outputs[0] == want


def test_corpus_reaches_every_step():
    text, want = corpus(16)
    ops = [line.split('\t')[0] for line in text.split('\n') if line]
    for op in ['R', 'M', 'L', 'L2', 'U', 'F', 'K', 'K2', 'C', 'D']:
        assert ops.count(op) >= 20 if op not in ('R', 'D') else ops.count(op) == 40, op
    # (copies of nonempty subtrees, children lists of every length, and every kind made)
    assert sum(1 for line in text.split('\n') if line.startswith('L\t') and line.count(',') >= 39) > 3
    assert {line.split('\t')[1] for line in text.split('\n') if line.startswith('M\t')} >= {str(i) for i in range(0, len(KINDS), 10)}


@pytest.mark.core_quick
def test_selfhost_node_store_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/node_store.dewy\0' in binary
    assert b'/compiler/node_store.jo\0' not in binary
