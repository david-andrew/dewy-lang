"""compiler/spelling.dewy, the checker's "did you mean" distance: it ships, and its
frozen implementation-language twin compiler/spelling.jo gives the same answers."""
import random
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

FIXTURES = Path(__file__).resolve().parent / 'fixtures/selfhost'


def build(compiler, source, binary, release):
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


def words():
    """Names and near misses of them: dropped, doubled, swapped and recased letters."""
    rng = random.Random(11)
    base = ['length', 'len', 'update', 'draw', 'score', 'SKYBLUE', 'push', 'remove',
            'velocity', 'x', 'ab', 'données', 'on_quit', 'main', '']
    out = list(base)
    for word in base[:-1]:
        for _ in range(3):
            w = list(word)
            i = rng.randrange(len(w))
            edit = rng.randrange(4)
            if edit == 0:
                del w[i]
            elif edit == 1:
                w.insert(i, w[i])
            elif edit == 2 and i + 1 < len(w):
                w[i], w[i + 1] = w[i + 1], w[i]
            else:
                w[i] = w[i].swapcase()
            out.append(''.join(w))
    return out


def distance(a: bytes, b: bytes, limit: int) -> int:
    """Optimal string alignment over ASCII-folded bytes, capped at limit + 1."""
    a, b = a.lower(), b.lower()
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return min(d[-1][-1], limit + 1)


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_selfhost_spelling_matches_jo(compiler, tmp_path, release):
    dewy = build(compiler, FIXTURES / 'spelling_dewy.dewy', tmp_path / 'spelling-dewy', release)
    jo = build(compiler, FIXTURES / 'spelling_jo.jo', tmp_path / 'spelling-jo', release)
    names = words()
    outputs = []
    for binary in (dewy, jo):
        ran = subprocess.run([binary, *names], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    lines = outputs[0].decode().splitlines()
    encoded = [n.encode() for n in names]
    pairs = [(limit, a, b) for limit in range(4) for a in encoded for b in encoded]
    # (past the limit the answer is only "too far": any number above it)
    got = [min(int(line), limit + 1) for line, (limit, _, _) in zip(lines, pairs)]
    assert got == [distance(a, b, limit) for limit, a, b in pairs]
    assert set(got) == {0, 1, 2, 3, 4}
    folded = [' '.join(str(c) for c in n.lower().encode()) for n in names]
    assert [line.rstrip() for line in lines[len(pairs):]] == folded


@pytest.mark.core_quick
def test_selfhost_spelling_ships_dewy(compiler, tmp_path):
    binary = compiler.read_bytes()
    assert b'/compiler/spelling.dewy\0' in binary
    assert b'/compiler/spelling.jo\0' not in binary
    source = tmp_path / 'hint.dewy'
    source.write_text('main=():>void=>{let total=1 printl(totla)}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert checked.returncode != 0
    assert "unknown name 'totla' (did you mean 'total'?)" in checked.stdout + checked.stderr
