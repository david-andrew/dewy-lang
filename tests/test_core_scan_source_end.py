"""The compiler's source scanners read nothing past the 0 after a source's last byte: every short
text (and the tails of some sources), its 0 the last byte of a mapped page, goes through the
lexer, the declaration scanner and the Dewy lexer (bodies lexed and skipped) without a fault.
A nil string (no bytes, no 0) lexes too. Errors in the texts are expected and stop only that
text (quiet_errors, __repl_jmp); a panic, a fault, fails the test."""
import itertools
import platform
import subprocess
import sys

import pytest

from tests.support import ROOT, compiler  # noqa: F401

HARNESS = '''
use '{root}/compiler/util.jo'
use '{root}/compiler/source_types.dewy'
use '{root}/compiler/check.jo'
use '{root}/compiler/lex.jo'
use '{root}/compiler/scan.jo'
use '{root}/compiler/dewy_fast.jo'

page = 4096
base = syscall(9, 0, 2 * page, 3, 0x22, -1, 0)
syscall(11, base + page, page)

# text in place, its 0 the page's last byte (no stale reference to the text before, which this
# one overwrites)
at_page_end = (text: str) -> str:
    lx_src = ""
    sc_src = ""
    files[1].src = ""
    n = len(text)
    h = (base + page - 1 - n - 24) as *int
    h[0] = 1 << 40
    h[1] = n
    h[2] = n + 1
    b = (h as *u8) + 24
    mem_copy(b, data(text), n)
    b[n] = 0
    h as str

jb: *u8 = null

scans = (m: int, s: str) -> bool:
    if __setjmp(jb) == 0:
        __repl_jmp = jb
        if m == 0: lex(0, s)
        else if m == 1: scan_source(s)
        else:
            files[1].src = s
            dn_skip_bodies = m == 3
            dn_lex(1, 0, len(s))
        __repl_jmp = null
        return true
    __repl_jmp = null
    false

quiet_errors = true
jb = __alloc(192)
files.push(SrcFile("t.jo", ".", "", false))
files.push(SrcFile("t.dewy", ".", "", true))
nil: str
loop m in [0..4): scans(m, nil)
texts = split(read_file(args()[1])!, "\\x01")
ran = 0
loop t in texts:
    loop m in [0..4):
        scans(m, at_page_end(t))
        ran += 1
print(ran)
'''

ALPHABET = [bytes([c]) for c in b'"\'\\{}#.<>=!-+*/%^&|~?:;,()[]@$`ax019_eErbf \n\t\r'] + [b'\x80', b'\xc3', b'\xff', b'\x00']
PREFIXES = [b'x = ', b'"', b'"{', b'"{a', b"'", b'"""', b"'''", b'#', b'#{', b'#[', b'`', b'0x',
            b'1.', b'a.', b'\n    ', b'r"', b'f(', b'=> {', b'{', b'"\\', b'"a{{', b'x="{', b'x=>',
            b'when a:\n', b'f = ():\n    ', b'1e', b'0b', b'"""a"', b'..']
SOURCES = ['compiler/lex.jo', 'compiler/scan.jo', 'compiler/dewy_lex.dewy', 'compiler/line_table.dewy',
           'lib/core/str.jo', 'lib/std/regex.jo']


def texts():
    out = [b''.join(t) for n in (1, 2, 3) for t in itertools.product(ALPHABET, repeat=n)]
    out += [p + b''.join(t) for p in PREFIXES for n in (1, 2) for t in itertools.product(ALPHABET, repeat=n)]
    # (the tails of real sources: one for each last four bytes, the 60 before them for context)
    seen = set()
    for name in SOURCES:
        src = (ROOT / name).read_bytes()
        for k in range(1, len(src) + 1):
            if src[max(0, k - 4):k] not in seen:
                seen.add(src[max(0, k - 4):k])
                out.append(src[max(0, k - 64):k])
    return [t for t in out if b'\x01' not in t]


@pytest.mark.core_quick
@pytest.mark.skipif(sys.platform != 'linux' or platform.machine() != 'x86_64', reason='x86-64 Linux mmap')
def test_scanners_stop_at_source_end(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'edge.jo'
    source.write_text(HARNESS.replace('{root}', str(ROOT)))
    inputs = tmp_path / 'texts'
    cases = texts()
    inputs.write_bytes(b'\x01'.join(cases))
    binary = tmp_path / 'edge'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary, inputs], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0 and 'panic' not in ran.stderr, ran.stdout[-2000:] + ran.stderr[-2000:]
    assert ran.stdout == f'{4 * len(cases)}\n'


@pytest.mark.core_quick
def test_hex_escape_at_text_end(compiler, tmp_path):  # noqa: F811
    """A `\\x` escape short of its two digits at the end of a text is an error, not a read past it."""
    source = tmp_path / 'hex.jo'
    source.write_text('print("\\x")\nprint("\\x4")\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'hex'], capture_output=True, text=True, timeout=300)
    assert built.returncode != 0 and 'panic' not in built.stderr, built.stderr
    assert 'bad \\x escape' in built.stderr, built.stderr
