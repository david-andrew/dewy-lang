"""Self-length arrays: the worked program against an independent reference, and their costs."""
import subprocess
from pathlib import Path

from tests.support import ROOT, compiler  # noqa: F401 (fixture)

CASE = ROOT / 'tests' / 'cases' / 'self_length' / 'worked_forest_permutation'


def generator_step(seed):
    return (seed * 1103515245 + 12345) % 2147483648


def forest_line():
    parent = list(range(64))

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != x:
            parent[x], x = root, parent[x]
        return root

    seed, joined = 7, 0
    for _ in range(48):
        seed = generator_step(seed)
        a = seed % 64
        seed = generator_step(seed)
        b = seed % 64
        x, y = find(a), find(b)
        if x != y:
            parent[x] = y
            joined += 1
    roots = checksum = 0
    for i in range(64):
        root = find(i)
        roots += root == i
        checksum = (checksum * 131 + root) % 1000000007
    return f'forest {joined} {roots} {checksum}'


def permutation_line():
    n, seed = 257, 42
    p = list(range(n))
    for i in range(1, n):
        seed = generator_step(seed)
        j = seed % (i + 1)
        p[i], p[j] = p[j], p[i]
    seen = [False] * n
    cycles = longest = 0
    for start in range(n):
        if seen[start]:
            continue
        cycles += 1
        size, at = 0, start
        while not seen[at]:
            seen[at] = True
            size += 1
            at = p[at]
        longest = max(longest, size)
    twice = 0
    for i in range(n):
        twice = (twice * 31 + p[p[i]]) % 1000000007
    return f'permutation {cycles} {longest} {twice}'


def list_line():
    following, head = [], -1
    for _ in range(100):
        following.append(-1)
        if head >= 0:
            following[-1] = head
        head = len(following) - 1
    total, at = 0, head
    while at >= 0:
        total += at
        at = following[at]
    return f'list {len(following)} {total}'


def test_worked_program_matches_the_reference():
    # (the golden runner checks the program's output against this file in every mode)
    assert CASE.with_suffix('.out').read_text().splitlines() == [forest_line(), permutation_line(), list_line()]


def test_worked_program_has_no_runtime_obligation(compiler, tmp_path):
    binary = tmp_path / 'worked'
    result = subprocess.run([compiler, '--internal-fact-policy=require-static', 'build', CASE.with_suffix('.dewy'), '-o', binary],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


def test_growth_and_swaps_stay_linear(compiler, tmp_path):
    # (a copy per push or per swap would take hours here)
    source = tmp_path / 'scale.dewy'
    source.write_text('''main=():>void=>{
    let p:array<int64<(<? p.length)>> = []
    loop _ in [0..2000000) { p.push(p.length) }
    let total = 0
    loop i in [1..p.length) {
        p.swap(i - 1 i)
        total += p[p[i]]
    }
    loop i in [0..p.length) { p[i] = p[p[i]] }
    printl(total)
}
''')
    binary = tmp_path / 'scale'
    result = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    p = list(range(2000000))
    total = 0
    for i in range(1, len(p)):
        p[i - 1], p[i] = p[i], p[i - 1]
        total += p[p[i]]
    assert ran.stdout.strip() == str(total)
