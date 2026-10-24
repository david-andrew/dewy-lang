"""The lexer reads nothing past the 0 after a source's last byte: a source that ends with an
operator's first byte, its 0 the last byte of a mapped page, lexes without a fault."""
import platform
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
@pytest.mark.skipif(sys.platform != 'linux' or platform.machine() != 'x86_64', reason='x86-64 Linux mmap')
def test_lex_stops_at_source_end(compiler, tmp_path):
    source = tmp_path / 'edge.jo'
    source.write_text(f"use '{ROOT / 'compiler/lex.jo'}'\nuse '{ROOT / 'compiler/check.jo'}'\n" + '''
lex_at_page_end = (text: str) -> int:
    page = 4096
    base = syscall(9, 0, 2 * page, 3, 0x22, -1, 0)
    syscall(11, base + page, page)
    n = len(text)
    h = (base + page - 1 - n - 24) as *int
    h[0] = 1 << 40
    h[1] = n
    h[2] = n + 1
    b = (h as *u8) + 24
    mem_copy(b, data(text), n)
    b[n] = 0
    toks = lex(0, h as str)
    toks.len()

loop text in ["f(x)", "a.", "a <", "a >", "x =", "a !", "\\"{{\\""]:
    print(lex_at_page_end(text) > 0)
''')
    binary = tmp_path / 'edge'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'true\n' * 7
