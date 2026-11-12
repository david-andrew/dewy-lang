"""Expectations, habits and the shared node builders agree with the frozen Jo parser."""
import subprocess

import pytest

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


def jo_text(s):
    """s as a Jo string literal (braces doubled, other bytes escaped)."""
    out = []
    for b in s.encode():
        c = chr(b)
        if c == '\\': out.append('\\\\')
        elif c == '"': out.append('\\"')
        elif c == '\n': out.append('\\n')
        elif c == '{': out.append('{{')
        elif c == '}': out.append('}}')
        elif 32 <= b < 127: out.append(c)
        else: out.append('\\x%02x' % b)
    return '"' + ''.join(out) + '"'


# Mistakes from other languages and plain expectation failures: each stops with its message.
MISTAKES = [
    'def add(a, b):\n    pass\n',
    'struct P:\n    def m(self):\n        pass\n',
    'x := 5\n',
    'f = ():\n    y = new HashMap()\n',
    'f = ():\n    y = new Vector3(1, 2, 3)\n',
    'f = ():\n    if a = b: c\n',
    'f = ():\n    x++\n',
    'f = ():\n    print "hi"\n',
    'f = ():\n    a = 7 // 2\n',
    'f = ():\n    for (i = 0; i < n; i++): g()\n',
    'f = ():\n    a = f"x{y}"\n',
    'f = ():\n    int x = 5\n',
    'f = ():\n    g(a b)\n',
    'f = ():\n    a = "she said "hi""\n',
    'f = (:\n',
    'f = ():\n    x = (1, 2\n',
    'let [a, b] = xs\n',
    'f = ():\n    loop x <= 3 then: g()\n',
    'f = ():\n    x = a ? b : c\n',
    'enum E = a, b\n',
    'f = ():\n    x = 1 2\n',
    'f = (a: int b: int): a\n',
    'x = (1,\n',
]

DRIVER = r'''use 'main.jo'
use 'parse.jo'
use 'parser_text.dewy'
use 'parser_shared.dewy'
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
    mistakes = [MISTAKES]
    a = args()
    if a.len() > 1:
        files = [SrcFile(path="mistake.jo", src=mistakes[to_int(a[1]) ?? 0])]
        nodes = [Node()]; lists = []
        parse_file(0)
        print("parsed")
        return
    src = "use 'x.jo'\nfrom m.n import (p, q as r)\nstruct S[T]:\n    a: T\n    b = 2\nenum E: x, y(int)\nf = (a: int, mut b: str) -> int:\n    let c, d = 1, 2\n    if let v = g(): h(v)\n    loop i in xs and j in 0..: k(&j)\n    return a.none\n"
    files = [SrcFile(path="ok.jo", src=src)]
    nodes = [Node()]; lists = []
    dump("parse:{parse_file(0)}")
    nodes = [Node()]; lists = []
    i = lx_ident("x", 7)
    c = lx_call("f", [lx_int(-3, 1), lx_bool(true, 2), lx_bool(false, 3)], 4)
    l = lx_let(intern("y"), lx_len(i, 5), 6)
    f = lx_if(lx_not(c, 8), lx_expr_stmt(lx_index(i, l, 9), 10), 11)
    lx_block([f, comp_ident(intern("z"), 12)], 13)
    loop op in [2, 3]:
        h = head_node(op, 14)
        x = head_node(4, 15)
        y = head_node(4, 16)
        nodes[h].a = i32(x)
        nodes[h].b = i32(y)
        head_collapse(h)
        z = head_node(op, 17)
        nodes[z].a = i32(x)
        nodes[z].b = i32(head_node(1, 18))
        head_collapse(z)
    dump("builders")
'''.replace('[MISTAKES]', '[' + ', '.join(jo_text(m) for m in MISTAKES) + ']')


@pytest.fixture(scope='module')
def binaries(compiler, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('shared')
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
        monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
        return leaf_compilers(compiler, tmp_path, ('parser_shared',))


def test_parser_shared_match_twin(binaries):
    outputs = [subprocess.run([binary], capture_output=True, timeout=60) for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout.count(b'case:') == 2


def test_parser_shared_mistakes_match_twin(binaries):
    for i in range(len(MISTAKES)):
        outputs = [subprocess.run([binary, str(i)], capture_output=True, timeout=60) for binary in binaries]
        assert outputs[0].returncode != 0, (i, outputs[0].stdout)
        assert ((outputs[0].returncode, outputs[0].stdout, outputs[0].stderr)
                == (outputs[1].returncode, outputs[1].stdout, outputs[1].stderr)), i
