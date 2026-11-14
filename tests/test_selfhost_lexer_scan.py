"""lex, lx_number and lx_string agree with their frozen lexer_scan twin.

Exercise byte spans, numerical boundaries, nested text, lazy bodies, retained
snapshots and token-array growth in both compiler modes.
"""
import subprocess

import pytest

from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'lex.jo'
use 'lexer_scan.dewy'
use 'source_types.dewy'
main = ():
    text = read_file(args()[2])!
    if args()[1] == "nil":
        empty: str
        text = empty
    files = [SrcFile(path="case.jo", src=text)]
    lx_lazy = args()[1] == "lazy"
    lx_base = 17
    begin = 0
    stop = -1
    if args()[1] == "span":
        begin = 3
        stop = len(text) - 3
    tokens = lex(0, text, begin, stop)
    saved = tokens
    # A fresh scan resets every header without changing the retained array.
    lx_lazy = false
    lx_base = 0
    again = lex(0, "replacement(7)\n")
    print("again:{again.len()}")
    loop t in saved:
        print("{int(t.kind)}:{t.flags}:{t.pos}:{t.start}:{t.len}:{t.ival}:{t.fval}")
    print("spare:{cap(saved) - saved.len() >= LX_SPARE}:{lx_slots == null}")
    p = data(saved)
    loop i in [0..LX_SPARE): assert(p[saved.len() + i].kind == Tok.eof)
'''

VALID = [
    ('nil', b''),
    ('normal', b''),
    ('normal', b'0 1 18446744073709551615 0xFFFFFFFFFFFFFFFF 0b101_010 0o77 0XAF 0B11 0O7\n'),
    ('normal', b'1.25 1e3 1E-2 1e+20 1_000.5_0 500ms 90deg 2s 0xffkg 1..2 1...2\n'),
    ('normal', b'a += 1; b -= 2; c *= 3; d /= 4; e %= 5; f &= 6; g |= 7; h ^= 8\n'
               b'x <<= 1; x >>= 2; a == b != c <= d >= e; !a ?? b ? c; @a ~b ** c -> d\n'
               b'[a, b] {a: b}; .+ .- .* ./ .% .^ .< .> .== .!= .<= .>= ...\n'),
    ('normal', b'"plain" \'single\' r"raw\\n{a}" r\'raw\' "escaped\\\"quote" "{{brace}}"\n'
               b'"{f({1: 2}, \'inner\')}" """multi\nline {x}""" "{"\n'),
    ('normal', 'caf\u00e9 = "e\u0301 \U0001f600"\n'.encode()),
    ('normal', b'raw\xffname = 7\n'),
    ('normal', b'foo = (x):\n    if x:\n        f(x)\n    else:\n        g(x)\n'
               b'x = f(():\n    a(), 5)\ny = [1,\n  2,\n  3]\n'),
    ('normal', b'a = 1 \\\n + 2 # ignored\n\t# comment\n'),
    ('span', b'###x = 42\n###'),
    ('lazy', b'f = (x):\n    if x:\n        "text"\n    else:\n        42\ng = (): 2\n'),
    ('normal', b'x = [' + b'a,' * 2048 + b'a]\n'),
]
ERRORS = [
    (b'18446744073709551616', b'integer literal too large'),
    (b'0x10000000000000000', b'integer literal too large'),
    (b'1e309', b'number too large'),
    (b'2bogus', b'unknown unit'),
    (b'0b12', b'invalid character in number literal'),
    (b'"unterminated', b'this text has no closing quote'),
    (b'"{x', b'unterminated string'),
    (b'"line\nnext"word', b'no closing quote on its line'),
    (b'(', b'this bracket is never closed'),
    (b')', b'unmatched'),
    (b'`', b'no backticks'),
    (b'\0', b'binary data'),
    (b'$"x"', b'drop the `$`'),
    (b'f(#xs)', b'`#` starts a comment'),
]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_lexer_scan_twins(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original_modules = selfhost_lsp_double.modules_for
    original_driver = selfhost_lsp_double.cached_driver

    def modules_for(*args, **kwargs):
        modules = dict(original_modules(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original_driver(compiler, path, release, modules))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_scan',))
    source = tmp_path / 'input.jo'
    cases = [(mode, text, 0, b'spare:true:true') for mode, text in VALID]
    cases += [('normal', text, 41, diagnostic) for text, diagnostic in ERRORS]
    for mode, text, status, expected in cases:
        source.write_bytes(text)
        runs = [subprocess.run([binary, mode, source], capture_output=True, timeout=30)
                for binary in binaries]
        assert [r.returncode for r in runs] == [status, status], (mode, text, [(r.stdout, r.stderr) for r in runs])
        assert (runs[0].stdout, runs[0].stderr) == (runs[1].stdout, runs[1].stderr), (mode, text)
        assert expected in runs[0].stdout, (mode, text, runs[0].stdout)
