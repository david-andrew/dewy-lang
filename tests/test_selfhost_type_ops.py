"""Type constructors, names, layout errors and the word overflow predicate agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

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
                print("{operation} {x} {y} {math_word_overflow(operation, x, y)}\\n")
'''


def test_type_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0


def test_math_word_overflow_twins(compiler, tmp_path):
    assert b'0 9223372036854775807 1 true' in compare_narrow(compiler, tmp_path, False, ['word_overflow'], OVERFLOW)
