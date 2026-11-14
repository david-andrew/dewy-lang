"""Source positions, shared lazy line state and bounded code-line scans match the twin."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = '''use 'source_types.dewy'
use 'line_table.dewy'
files: SrcFile[]
src_lines: LineTable
pos_file = (p: int) -> int: p >> 40
pos_off = (p: int) -> int: p & 0xFFFFFFFFFF
'''
DRIVER = r'''main = ():
    assert(line_col(-1) == (0, 0) and pos_str(-1) == "<unknown>")
    files = [SrcFile(path="/é.dewy", src="a\néx\nlast"), SrcFile(path="empty", src="")]
    loop p in [0, 1, 2, 4, 6, 9, 2, 0, 1 << 40, 2 << 40]:
        l, c = line_col(p)
        print("{pos_str(p)}:{l}:{c}")
    samples = ["é\n🦊", "", "\n", "# a\n", "a\nb", " \t\r\nx # rest\n", "a #{{ outer #{{ inner }}# tail }}# b\nc", "#{{ one\ntwo }}#\nx\n", "a\0b\n", "#{{unfinished"]
    loop text in samples:
        loop start in [0..len(text)+1):
            loop end in [start..len(text)+1): print("{start}:{end}:{code_lines(text, start, end)}")
    files[0].path = "renamed"
    assert(pos_str(2) == "renamed:2:1")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_source_queries_twins(compiler, tmp_path, release):
    out = compare_narrow(compiler, tmp_path, release, ('source_types', 'line_table', 'source_queries'),
                         DRIVER, doubles={'services.jo': SERVICES}, services=('util',))
    assert out.endswith(b'ok\n') and b'/\xc3\xa9.dewy:2:1:2:1\n' in out
