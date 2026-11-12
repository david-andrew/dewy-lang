"""Expression precedence and calls agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'lex.jo'
use 'lexer_helpers.dewy'
use 'ast.jo'
use 'util.jo'
use 'source_types.dewy'
use 'node_store.dewy'
use 'parser_expr.dewy'
main = ():
    init_keywords()
    loop text in [
        "1 + 2 * 3 ^ 4 ^ 5",
        "-2 ^ 3 + ~4",
        "not a and b or c xor d",
        "a not in b and c is not T",
        "a ?? b ?? c",
        "a..b + c",
        "f(x = 1 + 2, mut y, z ^ 2)",
        "a as T + b as U * c",
        "a .+ b .* c",
    ]:
        files = [SrcFile(path="expr.jo", src=text)]
        tokens = lex(0, text)
        p_toks = data(tokens); p_ntoks = tokens.len(); ti = 0
        p_src = text; p_file = 0; p_base = 0; p_matrix = 0
        nodes = [Node()]; lists = []
        root = parse_expr()
        print("case:{text}:root:{root}:end:{int(pk())}:nodes:{nodes.len()}")
        loop i in [1..nodes.len()):
            n = nodes[i]
            print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.nlist}")
'''


def test_parser_expr_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_expr',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 9
