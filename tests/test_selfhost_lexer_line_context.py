"""The line and token-buffer cutover agrees with its frozen Jo twin."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'lex.jo'
use 'lexer_helpers.dewy'
main = ():
    init_keywords()
    sources = [
        "a = 1\nb = 2\n",
        "# empty\n\nfoo = (x: int):\n    if x:\n        x + 1\n    else:\n        0\n",
        "f = (x):\n\tif x:\n\t\tx\n\telse:\n\t\t0\n",
        "xs = [1,\n      2,\n      3]\n",
        "when TARGET == \"linux\":\n    f = (): 1\nelse:\n    g = (): 2\n",
    ]
    long = ""
    loop i in [0..128): long += "name{i} = {i}\n"
    sources.push(long)
    loop src in sources:
        toks = lex(0, src)
        print("count:{toks.len()}")
        loop t in toks:
            print("{int(t.kind)}:{t.pos}:{t.start}:{t.len}:{t.flags}:{t.ival}")
'''


def test_lexer_line_context_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_line_context',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert b'count:' in outputs[0].stdout
