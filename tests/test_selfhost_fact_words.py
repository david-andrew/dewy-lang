"""Truncating host-word division agrees with frozen Jo at every sign and at the word's ends."""
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

DRIVER = r'''use 'fact_words.dewy'
values: int[] = [-9223372036854775807 - 1, -9223372036854775807, -4294967297, -65536, -9, -8, -7, -3, -2, -1, 0, 1, 2, 3, 7, 8, 9, 65536, 4294967297, 9223372036854775806, 9223372036854775807]
main = ():
    loop a in values:
        loop b in values:
            if b == 0 or (a == values[0] and b == -1): continue
            print("{a} {b} {fact_trunc_div(a, b)} {fact_trunc_rem(a, b)}\n")
'''


def test_fact_words_twins(compiler, tmp_path):
    assert b'-7 2 -3 -1' in compare_narrow(compiler, tmp_path, False, ['fact_words'], DRIVER)
