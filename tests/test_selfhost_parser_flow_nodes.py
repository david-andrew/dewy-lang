"""Legacy parser flow summaries, optional nodes and loop binders agree with Jo."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'parser_flow_nodes.dewy'
use 'parse.jo'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    nodes = [Node()]
    value = mk(.int_lit, 7)
    exit = mk(.break_, 7)
    ret = mk(.return_, 7); nodes[ret].a = i32(value)
    block = mk(.block, 7); set_list(block, [value, ret, exit])
    branch = mk(.if_, 7); nodes[branch].a = i32(value); nodes[branch].b = i32(ret); nodes[branch].c = i32(exit)
    lambda = mk(.lambda, 7); nodes[lambda].a = i32(ret)
    print("flow:{lx_flow_effects(0)}:{lx_flow_effects(value)}:{lx_flow_effects(exit)}:{lx_flow_effects(ret)}:{lx_flow_effects(block)}:{lx_flow_effects(branch)}:{lx_flow_effects(lambda)}")
    nodes[value].flags = i32(NF_FLOW_RETURNS); print("flag:{lx_flow_effects(value)}"); nodes[value].flags = 0
    nodes[ret].a = i32(exit); print("return-exit:{lx_flow_effects(ret)}")
    left = mk(.ident, 7); right = mk(.ident, 7); third = mk(.ident, 7)
    mid = mk(.binary, 7); nodes[mid].op = 3; nodes[mid].a = i32(left); nodes[mid].b = i32(right)
    root = mk(.binary, 7); nodes[root].op = 3; nodes[root].a = i32(mid); nodes[root].b = i32(third)
    out: int[] = []; lx_or_terms(root, mut out)
    print("terms:{out.len()}:{out[0] == left}:{out[1] == right}:{out[2] == third}")
    has = intern("present"); opt = lx_opt_value(has, value, 19)
    print("option:{nodes[opt].kind == .if_}:{name_of(int(nodes[int(nodes[opt].a)].name))}:{nodes[int(nodes[kid(int(nodes[opt].c), 0)].a)].kind == .none_lit}")
    loop text in ["(x in xs)", "(mut x in xs)", "(x+1)", "(call x in xs)", "((x in xs))", "()"]:
        files = [SrcFile(path="case.jo", src=text)]
        tokens = lex(0, text); p_toks = data(tokens); p_ntoks = tokens.len()
        print("binder:{head_has_binder(0)}")
'''


def test_parser_flow_nodes_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_flow_nodes',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (b'flow:1:1:4:2:2:6:1', b'flag:2', b'return-exit:4',
                     b'terms:3:true:true:true', b'option:true:present:true',
                     b'binder:true\nbinder:true\nbinder:false\nbinder:false\nbinder:true\nbinder:false'):
        assert expected in outputs[0].stdout
