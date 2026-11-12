"""Token ordinals, keyword and precedence queries and the operator builders agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_ops.dewy'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'checker_tokens.dewy'
use 'util.jo'
main = ():
    init_keywords()
    loop i in [0..int(Tok.lazy) + 1):
        k = i as Tok
        print("tok:{i}:{int(tok_ordinal(k))}:{tok_ordinal(k) == i32(i)}:{is_keyword_tok(k)}:{binprec(k)}:{binprec_value(k)}")
    nodes = [Node()]; lists = []
    loop i in [0..int(Tok.lazy) + 1):
        k = i as Tok
        b = lx_bin(k, i, i + 1, i * 3)
        a = lx_assign(b, k, i, i * 5)
        print("ops:{b}:{nodes[b].op}:{nodes[b].a}:{nodes[b].b}:{nodes[b].pos}:{a}:{nodes[a].op}:{nodes[a].a}:{nodes[a].b}:{nodes[a].pos}:{int(nodes[a].kind)}")
'''


def test_parser_ops_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_ops',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60) for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    lines = outputs[0].stdout.decode().splitlines()
    toks = [line for line in lines if line.startswith('tok:')]
    assert len(toks) == 87 and all(':true:' in line for line in toks)
    assert sum(line.startswith('ops:') for line in lines) == 87
