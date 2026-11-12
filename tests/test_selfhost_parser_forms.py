"""Primary, postfix, bracket and function forms agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_forms.dewy'
use 'parser_expr.dewy'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    init_keywords()
    loop text in [
        "42", "true", "none", "_", ".name", "(a, b)", "[1, 2, 3]",
        "[1 2; 3 4]", "[1..3]", "a[0]", "a[..b)", "a[1, 2]",
        "f(x = 1, mut y)", "x.field!", "x.0.1", "(x: int): x + 1",
        "if a: b else: c", "\{1: 2}",
    ]:
        files = [SrcFile(path="forms.jo", src=text)]
        tokens = lex(0, text)
        p_toks = data(tokens); p_ntoks = tokens.len(); ti = 0
        p_src = text; p_file = 0; p_base = 0; p_matrix = 0
        p_header = false; p_no_tuple = false; p_top_decl = false; p_index = []
        nodes = [Node()]; lists = []
        root = parse_expr()
        print("case:{text}:root:{root}:end:{int(pk())}:nodes:{nodes.len()}")
        loop i in [1..nodes.len()):
            n = nodes[i]
            print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.nlist}")
'''


def test_parser_forms_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_forms',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 18
