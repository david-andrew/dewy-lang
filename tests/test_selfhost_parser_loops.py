"""Loop heads and their lowering agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_text.dewy'
use 'parser_loops.dewy'
use 'parser_cursor.dewy'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
dump = (label: str):
    print("case:{label}:nodes:{nodes.len()}:lists:{lists}")
    loop i in [1..nodes.len()):
        n = nodes[i]
        print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.sval}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.list}:{n.nlist}")
main = ():
    init_keywords()
    # whole loops through parse_stmt: heads, unpacking and combined lowering
    loop text in [
        "f = ():\n    loop:\n        g()\n    loop let v = next(): g(v)\n    loop x < 3: g(x)\n",
        "f = ():\n    loop x in xs: g(x)\n    loop mut x in xs: g(x)\n    loop k, v in m: g(k)\n    loop a, b, c in ts: g(a)\n",
        "f = ():\n    loop k, mut v in m: g(v)\n    loop i in 0,2..10: g(i)\n",
        "f = ():\n    loop x in xs and x > 0: g(x)\n    loop i in 0.. and x in xs: g(i)\n",
        "f = ():\n    loop i in 1.. and x in xs: g(i)\n    loop x in xs and y in ys: g(x, y)\n",
        "f = ():\n    loop c > 0 and x in xs and i in 0..: g(i)\n    loop (x in xs and y in ys) and z < 2: g(z)\n",
        "f = ():\n    loop x in xs or y in ys: g(x, y)\n    loop i in [0..3) or j in [0..5]: g(i)\n",
        "f = ():\n    loop i in [0..n) and j in [0..m] and x in xs: g(i)\n    loop i in 0.. and j in 5..: g(i)\n",
        "f = ():\n    loop i in 0.. or j in [1..4]: g(i)\n    loop mut x in xs and i in 0..: g(x)\n",
        "f = ():\n    loop i in 0.. and p, q in pairs: g(p)\n    loop a < 1 or b < 2: g()\n",
    ]:
        files = [SrcFile(path="loops.jo", src=text)]
        nodes = [Node()]; lists = []
        decls = parse_file(0)
        dump(text)
    # a Dewy loop with an else arm (c), lowered with its entry flag, in a .dewy file
    loop text in ["loop x in xs and i in 0..:", "loop x in xs or y in ys:", "loop i in [0..3) and j in 2..:"]:
        files = [SrcFile(path="loops.dewy", src=text, is_dewy=true)]
        tokens = lex(0, text)
        p_toks = data(tokens); p_ntoks = tokens.len(); ti = 0
        p_src = text; p_file = 0; p_base = 0; p_matrix = 0
        nodes = [Node()]; lists = []
        lx = parse_loop_head()
        body = mk(.block, 0)
        stmt = mk(.break_, 0)
        set_list(body, [stmt])
        other = mk(.block, 0)
        set_list(other, [mk(.return_, 0)])
        nodes[lx].b = i32(body)
        nodes[lx].c = i32(other)
        root = desugar_loopx(lx)
        dump("{text}:root:{root}")
'''


def test_parser_loops_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_loops',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 13
