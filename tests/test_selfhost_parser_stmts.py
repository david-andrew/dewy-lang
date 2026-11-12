"""Blocks and statements agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_text.dewy'
use 'parser_stmts.dewy'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    init_keywords()
    loop text in [
        "f = ():\n    return 1, 2\n    return\n",
        "f = ():\n    loop i in xs:\n        if i > 0: break\n        continue\n    pass\n",
        "f = ():\n    defer:\n        close()\n    defer g()\n",
        "f = ():\n    let a, _, c = t\n    let d: int = 1, 2\n    x: f64 = 0.5\n",
        "f = ():\n    a, b = b, a\n    xs .+= ys\n    n ^= 2\n",
        "f = ():\n    a and= b\n    a or= b\n    a xor= b\n    a += 1; b -= 2\n",
        "f = ():\n    if let t = e and t != 0 and u: g(t)\n    else: h()\n",
        "f = ():\n    if a: b\n    else if c:\n        d\n    else: e\n",
        "f = ():\n    match x:\n        .a, b(p, q): 1\n        _: 2\n        1..3: 3\n        else: 4\n",
        "f = ():\n    ys = [loop x in xs: if x > 0: x * 2]\n    m = \{loop k in ks: if let v = g(k): k: v}\n",
        "f = ():\n    zs = [loop a in ps: loop b in bs: a + b]\n",
        "f = ():\n    when A: x = 1\n    loop i < 3: g()\n    const K: int = 3\n",
        "f = (): x = 1\ng = (x: int): x, 2\n",
    ]:
        files = [SrcFile(path="stmts.jo", src=text)]
        nodes = [Node()]; lists = []
        decls = parse_file(0)
        print("case:{text}:decls:{decls}:nodes:{nodes.len()}:lists:{lists}")
        loop i in [1..nodes.len()):
            n = nodes[i]
            print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.sval}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.list}:{n.nlist}:{n.list2}:{n.nlist2}")
'''


def test_parser_stmts_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_stmts',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 13
