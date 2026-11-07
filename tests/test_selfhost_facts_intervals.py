"""Interval arithmetic reads in diagnostics: every operator's bounds agree with frozen Jo across signs and word ends."""
import itertools
import subprocess

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

FUNCTION = '''pick{index}=(xs:array<int64> a:{word} b:{word}):>int64=>{{
    if a >=? {a_lo} and a <=? {a_hi} and b >=? {b_lo} and b <=? {b_hi} {{
        let v=int64({expr})
        return xs[v]
    }}
    0
}}
'''
DIVIDENDS = [(-7, 5), (-9, -2), (3, 100), (-7, -7), (-9223372036854775807, -1), (1, 9223372036854775807)]
DIVISORS = [(2, 3), (-3, -2), (2, 2), (1, 8)]
OPERATORS = ['a // b', 'a % b', 'a & b', 'a | b', 'a xor b', 'min(a b)', 'max(a b)', 'a * b', '(a + b) // 2']
SHIFTS = ['a >> b', 'a << b']
COUNTS = [(0, 3), (1, 1), (0, 63), (62, 62)]


def program(tmp_path, word, forms):
    """One program whose every function fails a bound and reports the operator's interval."""
    text = ''.join(FUNCTION.format(index=i, word=word, a_lo=a[0], a_hi=a[1], b_lo=b[0], b_hi=b[1], expr=expr)
                   for i, (a, b, expr) in enumerate(forms))
    (tmp_path / f'{word}.dewy').write_text(text + 'main=()=>{\n    printl(0)\n}\n')
    return str(tmp_path / word)


def test_facts_intervals_twins(compiler, tmp_path, monkeypatch):
    words = [program(tmp_path, 'int64', [*itertools.product(DIVIDENDS, DIVISORS, OPERATORS), *itertools.product(DIVIDENDS, COUNTS, SHIFTS)]),
             program(tmp_path, 'int', [*itertools.product(DIVIDENDS[:3], DIVISORS[:2], OPERATORS[:2])]),
             program(tmp_path, 'uint64', [*itertools.product([(3, 100), (9223372036854775808, 18446744073709551615)], [(2, 3), (1, 63)], OPERATORS[:5] + SHIFTS)])]
    compare_facts(compiler, tmp_path, monkeypatch, words)
    shown = subprocess.run([compiler, 'build', words[0] + '.dewy', '-o', tmp_path / 'program'], capture_output=True, text=True)
    assert 'is between -4 and 2' in shown.stderr + shown.stdout
