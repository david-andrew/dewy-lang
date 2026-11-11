"""Legacy parser position queries and end-index construction agree with Jo."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'parser_positions.dewy'
use 'parse.jo'
use 'lex.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'source_types.dewy'
use 'util.jo'
main = ():
    p_src = "a é\n  z"
    tokens = [Token(kind=.ident, start=0, len=1, pos=mkpos(2, 10)), Token(kind=.ident, start=2, len=2, pos=mkpos(2, 12)), Token(kind=.ident, start=7, len=1, pos=mkpos(2, 17)), Token(kind=.eof, start=8, pos=mkpos(2, 18))]
    p_toks = data(tokens); p_ntoks = tokens.len()
    ti = 0; print("prev0:{prev_end() == mkpos(2, 10)}")
    ti = 1; print("prev1:{prev_end() == mkpos(2, 11)}")
    ti = 3; print("prev3:{prev_end() == mkpos(2, 18)}")
    print("next:{nk_is(0, .ident)}:{nk_is(1, .eof)}:{nk_is(2, .eof)}:{nk_is(3, .eof)}")
    print("newline:{nl_before(0)}:{nl_before(1)}:{nl_before(2)}:{nl_before(3)}")
    files = [SrcFile(path="indent.jo", src="  é\n\t z\nplain\n   ")]
    print("indent:{line_indent(mkpos(0, 0))}:{line_indent(mkpos(0, 2))}:{line_indent(mkpos(0, 4))}:{line_indent(mkpos(0, 7))}:{line_indent(mkpos(0, 9))}:{line_indent(mkpos(0, 17))}")
    nodes = [Node()]
    original = mk(.ident, 3); nodes[original].name = i32(intern("items"))
    p_index = [original]
    result = index_end(47)
    call = int(nodes[result].a); one = int(nodes[result].b)
    callee = int(nodes[call].a); cloned = kid(call, 0)
    print("end:{nodes[result].kind == .binary}:{nodes[result].op == i32(int(Tok.minus))}:{nodes[result].pos}:{nodes[call].kind == .call}:{name_of(int(nodes[callee].name))}:{cloned != original}:{nodes[cloned].name == nodes[original].name}:{nodes[one].kind == .int_lit}:{nodes[one].ival}:{(int(nodes[one].flags) & NF_LITERAL) != 0}")
    print("original:{nodes[original].pos}:{name_of(int(nodes[original].name))}")
'''


def test_parser_positions_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_positions',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (b'prev0:true', b'prev1:true', b'prev3:true',
                     b'next:true:false:true:false', b'newline:true:false:true:false',
                     b'indent:2:2:2:2:0:3',
                     b'end:true:true:47:true:len:true:true:true:1:true', b'original:3:items'):
        assert expected in outputs[0].stdout
