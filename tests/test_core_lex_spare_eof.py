"""The parser looks a few tokens ahead without bounds checks: every token array the lexer
gives has zeroed slots after its eof, read as more eofs, also when the tokens fill the
array's capacity exactly. Sources sized to land on each capacity lex and parse."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_token_array_spare_eofs(compiler, tmp_path):
    source = tmp_path / 'spare.jo'
    uses = ''.join(f"use '{ROOT / 'compiler' / name}'\n" for name in ('util.jo', 'lex.jo', 'parse.jo', 'check.jo'))
    source.write_text(uses + '''
# the capacities the lexer's token array takes for text of n bytes (lex in compiler/lex.jo)
capacities = (n: int) -> int[]:
    out: int[]
    c = n / 5 + 16
    loop c < 1 << 20:
        out.push(c)
        c = c * 2 + 16
    out

exact = 0
short = 0
parsed = 0
loop shape in [0..3):
    loop n in [0..700):
        text = ""
        if shape == 0: text = "x = f(" + repeat("a, ", n) + "a)\\n"
        else if shape == 1: text = "x = a" + repeat(" + a", n)
        else: text = "g = (xs: int[]):\\n    loop " + repeat("b, ", n) + "b in xs:\\n        pass"
        toks = lex(0, text)
        if capacities(len(text)).contains(toks.len()): exact += 1
        p = data(toks)
        ok = cap(toks) - toks.len() >= 8
        loop k in [0..8):
            if ok and p[toks.len() + k].kind != Tok.eof: ok = false
        if not ok: short += 1
        files.push(SrcFile(path = "edge.jo", src = text))
        parsed += parse_file(files.len() - 1).len()
print("{exact > 0} {short} {parsed}")
''')
    binary = tmp_path / 'spare'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'true 0 2100\n'
