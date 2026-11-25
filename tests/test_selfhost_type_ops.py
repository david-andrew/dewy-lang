"""Type constructors, names, layout errors and the word overflow predicate agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

CASES = [
    'misc/unsigned_constant_math',
    'union_hash/member_hash',
    'generic/local_arity',
    'units/parameter_mismatch',
]
OVERFLOW = r'''use 'word_overflow.dewy'
values: int[] = [-9223372036854775807 - 1, -9223372036854775807, -4294967296, -3037000500, -2, -1, 0, 1, 2, 3, 63, 64, 3037000500, 4294967296, 9223372036854775806, 9223372036854775807]
main = ():
    loop operation in [0..5):
        loop x in values:
            loop y in values:
                print("{operation} {x} {y} {math_word_overflow(operation, x, y)}")
'''


def test_type_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0


def test_math_word_overflow_twins(compiler, tmp_path):
    out = compare_narrow(compiler, tmp_path, False, ['word_overflow'], OVERFLOW, snapshot=False)
    values = [int(x) for x in OVERFLOW.split('values: int[] = [', 1)[1].split(']\n', 1)[0]
              .replace('-9223372036854775807 - 1', '-9223372036854775808').split(', ')]
    expected = []
    low, high = -(1 << 63), (1 << 63) - 1
    for op in range(5):
        for x in values:
            for y in values:
                if op == 3:
                    overflow = y == 0 or (x == low and y == -1)
                elif op == 4:
                    overflow = y < 0 or (x != 0 if y >= 64 else not low <= x << y <= high)
                else:
                    overflow = not low <= (x + y, x - y, x * y)[op] <= high
                expected.append(f'{op} {x} {y} {str(overflow).lower()}'.encode())
    assert out.splitlines() == expected
