from tests.selfhost_expr_double import print_warnings
"""Checker metadata spelling, fixed-size names and browser warnings agree with the frozen Jo leaf."""
import re
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'check_metadata.dewy'
use 'checker_tokens.dewy'
use 'checker_state.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'check.jo'
main = ():
    files = [SrcFile(path="case.dewy", src=" use", is_dewy=true), SrcFile(path="case.jo", src=" use", is_dewy=false)]
    nodes = [Node()]
    loop word in ["str", "byte", "f32", "f64", "i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "int64", "unknown"]:
        print("type:{word}:{dewy_type_word(word)}")
    loop op in [Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.eq, Tok.ne, Tok.plus]:
        print("op:{op_text(op, mkpos(0, 1))}:{op_text(op, mkpos(1, 1))}:{op_text(op, 0)}")
    tn = mk(.tname, mkpos(0, 1)); a = mk(.tname, 0); nodes[a].name = i32(intern("N"))
    print("size-empty:{fixed_size_arg(tn)}")
    set_list(tn, [a]); print("size-unbound:{fixed_size_arg(tn)}")
    init = mk(.int_lit, 0); nodes[init].ival = 4
    globals = [Global(init=i32(init))]; syms = [Sym()]
    s = new_sym(int(nodes[a].name), .const_, 0, 0); push_scope_sym(int(nodes[a].name), s)
    print("size-const:{fixed_size_arg(tn)}")
    nodes[a].sval = 1; print("size-string:{fixed_size_arg(tn)}"); nodes[a].sval = 0
    set_list(a, [init]); print("size-nested:{fixed_size_arg(tn)}"); set_list(a, [])
    nodes[a].kind = .ident; print("size-value:{fixed_size_arg(tn)}")
    decl = mk(.fn_, 0); nodes[decl].name = i32(intern("render"))
    attrs = mk(.block, 0); nodes[decl].c = i32(attrs)
    attr = mk(.call, 0); nodes[attr].name = i32(intern("no_web"))
    msg = mk(.str_lit, 0); nodes[msg].sval = i32(intern("has no browser effect")); nodes[attr].a = i32(msg)
    set_list(attrs, [attr]); no_web_check(decl, 0)
    no_web_check(decl, mkpos(0, 1)); no_web_check(decl, mkpos(0, 1))
    print("done")
'''


def test_check_metadata_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        print_warnings(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('check_metadata',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (b'type:f32:float32', b'op:<?:<:<', b'size-empty:false',
                     b'size-unbound:false', b'size-const:true', b'size-string:false',
                     b'size-nested:false', b'size-value:false', b'done'):
        assert expected in outputs[0].stdout
    assert outputs[0].stdout.count(b'render has no browser effect') == 1
