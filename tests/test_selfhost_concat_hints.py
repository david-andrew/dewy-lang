"""Concat fix-it pieces and diagnostic paths agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'concat_hints.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'util.jo'
use 'type_ops.dewy'
use 'types.jo'
main = ():
    init_types()
    files = [SrcFile(path="case.dewy", src="left + right", is_dewy=true)]
    nodes = [Node()]
    a = mk(.ident, mkpos(0, 0)); nodes[a].name = i32(intern("left"))
    b = mk(.ident, mkpos(0, 7)); nodes[b].name = i32(intern("right"))
    n = mk(.binary, mkpos(0, 5))
    op = args()[1]
    if op == "text": no_concat_error(n, a, b, true)
    if op == "mixed": no_concat_error(n, a, b, false)
    if op == "array":
        nodes[a].type = i32(mk_array(T_INT)); nodes[b].type = nodes[a].type
        no_concat_error(n, a, b, false)
    print("ident:{concat_piece(a, true)}:{concat_piece(b, false, true)}")
    nodes[a].name = i32(intern("$tmp"))
    print("hidden:{concat_piece(a, true)}:{concat_piece(a, false)}:{concat_piece(a, true, true)}:{concat_piece(a, false, true)}")
    nodes[a].name = i32(intern("line"))
    lit = mk(.str_lit, 0); nodes[lit].sval = i32(intern("literal"))
    print("literal:{concat_piece(lit, true)}")
    start = mk(.int_lit, 0); nodes[start].ival = 2
    end = mk(.int_lit, 0); nodes[end].ival = 5
    inc = mk(.bool_lit, 0); bounded = mk(.bool_lit, 0); nodes[bounded].ival = 1
    call = mk(.call, 0); set_list(call, [a, start, end, inc, bounded])
    print("slice:{concat_slice_text(call)}")
    nodes[inc].ival = 1
    print("inclusive:{concat_slice_text(call)}")
    nodes[bounded].ival = 0
    print("open:{concat_slice_text(call)}")
    field = mk(.field, 0); nodes[field].a = i32(a); nodes[field].name = i32(intern("keys"))
    print("field:{concat_piece(field, true)}")
    nodes[field].aux = -2; nodes[field].ival = 3
    print("tuple:{concat_piece(field, true)}")
    print("number:{concat_piece(start, true)}")
'''


def test_concat_hints_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('concat_hints',))
    for op, code, expected in [('pieces', 0, b'slice:line[2..5)'),
                               ('text', 41, b'"{left}{right}"'),
                               ('mixed', 41, b'`+` is reserved for elementwise math'),
                               ('array', 41, b'[left... right...]')]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        if op == 'pieces':
            assert b'hidden:{x}:xs:{y}:ys' in outputs[0].stdout
            assert b'literal:literal' in outputs[0].stdout
            assert b'inclusive:line[2..5]' in outputs[0].stdout
            assert b'open:line[2..]' in outputs[0].stdout
