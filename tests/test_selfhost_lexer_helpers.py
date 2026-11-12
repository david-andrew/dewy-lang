"""Lexer helper execution agrees with the frozen Jo twin."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'lex.jo'
use 'lexer_helpers.dewy'
main = ():
    init_keywords()
    loop k in [Tok.kw_if, Tok.kw_return, Tok.pluseq, Tok.dotop, Tok.kw_is, Tok.eof]:
        print("text:{tok_text(k)}")
    loop b in [u8(0), u8('a'), u8('Z'), u8('_'), u8('5'), u8(0x80), u8(255)]:
        print("ident:{int(b)}:{is_ident_start(b)}:{is_ident_char(b)}:{hexval(b)}")
    loop src in [
        "a = 1\nb = 2\n",
        "foo = (x: int):\n    if x:\n        x + 1\n    else:\n        0\n",
        "f = (x):\n\tif x:\n\t\tx\n\telse:\n\t\t0\n",
        "xs = [1,\n      2,\n      3]\n",
        "when TARGET == \"linux\":\n    f = (): 1\nelse:\n    g = (): 2\n",
        "x = 2.5e3\ny = 0.000000000000123456789\nz = 1_234.5\n",
        "a = r\"raw \\ text\"\nb = \"hello {{name}}\"\n",
    ]:
        toks = lex(0, src)
        print("count:{toks.len()}")
        loop t in toks:
            print("{int(t.kind)}:{t.pos}:{t.start}:{t.len}:{t.flags}:{t.ival}:{t.fval}")
    lx_src = "\"abc\"\n"
    lx_p = data(lx_src); lx_n = len(lx_src)
    print("skip:{lx_skip_str(0, false)}:{lx_body_end(0, 0)}")
'''


def test_lexer_helpers_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_helpers',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert b'count:' in outputs[0].stdout
