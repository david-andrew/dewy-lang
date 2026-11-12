"""Type forms and top-level declarations agree with the frozen Jo parser."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_decls.dewy'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    init_keywords()
    loop text in [
        "type Pair = (int, str)\ntype R[T, E] = T | E | none\n",
        "f = (a: int, b: *u8) -> int: a\ng[T] = (x: T) -> T: x\n",
        "(+) = (a: V, b: V) -> V: a\n([]) = (a: V, i: int) -> int: i\n",
        "extern puts = (s: *u8) -> int\nh = (cb: cfn(int, *u8) -> int) -> void: 0\n",
        "struct P[T]:\n    x: T\n    y = 2\nstruct Q:\n    pass\n",
        "enum E: a, b(int, name: str), c = 3\nenum F[T]:\n    a,\n    b(T)\n    c\n",
        "from a.b import (x,\n    y as z)\nuse 'lib/thing.jo' as t\nimport std.json\nfrom 'p/q.jo' import w\n",
        "test \"t\":\n    x = 1\nbuild:\n    y = 2\n",
        "when A == 1:\n    x = 1\nelse when B:\n    y = 2\nelse:\n    z = 3\n",
        "when A: v = 1\nelse if B: v = 2\n",
        "@inline\n@warn_if(a, \"m\")\nk = (): 0\n",
        "m: \{str: int[]} = x\np: soa P[] = y\nq: **u8? = null\n",
        "fp: (int, mut str) -> void = n\nt2: (int, str)[,] = e\na: int[4] = s\nb: T[N]? = y\n",
        "c: mod.Name[int, str] = z\nu: int | str[] | none = 0\nd: (int) = 1\n",
    ]:
        files = [SrcFile(path="decls.jo", src=text)]
        nodes = [Node()]; lists = []
        decls = parse_file(0)
        print("case:{text}:decls:{decls}:nodes:{nodes.len()}:lists:{lists}")
        loop i in [1..nodes.len()):
            n = nodes[i]
            print("node:{i}:{int(n.kind)}:{n.op}:{n.a}:{n.b}:{n.c}:{n.name}:{n.sval}:{n.ival}:{n.flags}:{n.aux}:{n.aux2}:{n.list}:{n.nlist}:{n.list2}:{n.nlist2}")
'''


def test_parser_decls_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_decls',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 14
