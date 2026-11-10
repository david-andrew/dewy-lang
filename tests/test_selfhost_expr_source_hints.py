"""Source diagnostic helpers agree with frozen Jo, including arbitrary byte excerpts."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'expr_source_hints.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'type_ops.dewy'
use 'types.jo'
use 'checker_tokens.dewy'
main = ():
    init_types()
    files = [SrcFile(path="test.dewy", src="  x as Box<int64>  ", is_dewy=true)]
    nodes = [Node()]
    a = mk(.ident, mkpos(0, 2))
    ty = mk(.tname, mkpos(0, 7))
    cast = mk(.cast, mkpos(0, 2)); nodes[cast].a = i32(a); nodes[cast].b = i32(ty)
    print("source:{regroup_source(0, 0, files[0].src.len())};type:{regroup_type_text(cast)}")
    loop text in ["abc", "(x)", "[x]", ")x", "([x])", "x)", "(x"]:
        print("balanced:{text}:{regroup_balanced(text)}")
    loop kind in [NK.and_, NK.or_, NK.not_, NK.binary]:
        op = mk(kind, mkpos(0, 2)); nodes[op].op = i32(int(Tok.plus))
        print("op:{regroup_op_name(op)}")
    files[0].src = "\{  x}"
    nodes[a].pos = mkpos(0, 3)
    print("interpolation:{written_interpolation(a)}:{node_within(cast, a)}:{node_within(a, cast)}:{node_within(cast, a, 65)}")
    files[0].src = " xx" + byte_str(255) + "yy "
    print("bytes:{regroup_source(0, 0, files[0].src.len())}")
    print("optional:{optional_hint(a, mk_opt(T_INT))}:{optional_hint(a, mk_opt(mk_opt(T_INT)))}")
'''


def test_source_hints_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('expr_source_hints',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert outputs[0].stdout == outputs[1].stdout and outputs[0].stderr == outputs[1].stderr
    assert b'\xff' in outputs[0].stdout
