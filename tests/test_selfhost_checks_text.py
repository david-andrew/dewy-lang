"""Byte positions in text and symbol kind ordinals agree with frozen Jo, on text with multi-byte characters."""
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

DRIVER = '''main = ():
    texts = ["", "a", "abcabc", "é(x(é", "((", "日本語.dewy"]
    parts = ["", "a", "(", "bc", "é", "語", ".dewy", "zzzzzzzzzzzz"]
    loop t in texts:
        loop p in parts:
            print("{byte_rfind(t, p)}")
            loop start in [-1, 0, 1, 2, 3, 40]:
                print("{byte_find(t, p, start)}")
    loop k in [0..12): print("{sym_kind_ordinal(sym_kind_of(k))}")
'''


def test_checks_text_twins(compiler, tmp_path):
    assert compare_narrow(compiler, tmp_path, False, ['checks_text'], DRIVER)
