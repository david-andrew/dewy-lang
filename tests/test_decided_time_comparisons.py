"""Duration ordering uses exact quantities, without grid or width narrowing."""
from fractions import Fraction
import random
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_duration_quantity_comparisons_match_fractions(compiler, tmp_path, release):
    rng = random.Random(17128)
    samples = [(0, 1, 3), (0, -1, 3), (1, 1, 1),
               ((1 << 127) - 1, 1 << 127, 1),
               (-(1 << 127), -(1 << 127) - 1, 1),
               (0, 10**100, 1), (0, -(10**100), 1)]
    for _ in range(64):
        count = rng.randrange(-(1 << 127), 1 << 127)
        numerator = rng.randrange(-(1 << 450), 1 << 450)
        denominator = rng.randrange(1, 1 << rng.choice((8, 64, 200, 400)))
        samples.append((count, numerator, denominator))
    lines, expected = [], []
    for count, numerator, denominator in samples:
        lines.append(f'show({count} {numerator} {denominator})')
        q = Fraction(numerator, denominator)
        tests = (count < q, count <= q, count == q, count != q, count >= q, count > q,
                 q < count, q <= count, q == count, q != count, q >= count, q > count)
        expected.append(' '.join(str(value).lower() for value in tests))
    source = tmp_path / 'comparisons.dewy'
    source.write_text('''import p"@lib/time/core.dewy" as core
show=(count:int numerator:int denominator:int<(>? 0)>):>void=>{
    let d=core.duration_of(count)
    let q=rational(numerator denominator)*ns
    printl"{d <? q} {d <=? q} {d =? q} {d not=? q} {d >=? q} {d >? q} {q <? d} {q <=? d} {q =? d} {q not=? d} {q >=? d} {q >? d}"
}
''' + '\n'.join(lines) + '\n')
    result = subprocess.run([compiler, source, *(['--release'] if release else [])],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == expected
