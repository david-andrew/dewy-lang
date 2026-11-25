"""Game call diagnostics preserve byte positions, literal spellings and shader-uniform lookup."""

import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


DRIVER = r'''use 'main.jo'
use 'game_call_checks.dewy'
use 'source_types.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'util.jo'
use 'check.jo'
use 'checker_state.dewy'
main = ():
    init_types()
    files = [SrcFile(path="game.jo", src=" 45 ), 6.0)")]
    nodes = [Node()]
    a = mk(.int_lit, mkpos(0, 1)); nodes[a].ival = 45; add_flag(a, NF_LITERAL)
    b = mk(.float_lit, mkpos(0, 7)); nodes[b].fval = 6.0; add_flag(b, NF_LITERAL)
    print(written_int(a), written_int(b))
    param = mk(.param, 0); nodes[param].name = i32(intern("angle"))
    decl = mk(.fn_, 0); nodes[decl].name = i32(intern("rotation_y")); set_list(decl, [param])
    shader_draw_check(decl, [a])
    angle_check(decl, [a])
    fns.push(FnInst(ptypes=[T_VEC2, T_INT], ret=i32(T_VEC4)))
    ref = mk(.fnref, 0); nodes[ref].sym = i32(fns.len() - 1)
    call = mk(.call, 0); set_list(call, [ref])
    print(shader_uniforms_in(call) == T_INT, shader_uniforms_in(decl) == 0)
'''


def test_game_call_checks_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('game_call_checks',))
    results = [subprocess.run([b], capture_output=True, timeout=30) for b in binaries]
    left, right = results
    assert left.returncode == right.returncode == 0
    assert (left.stdout, left.stderr) == (right.stdout, right.stderr)
    assert left.stdout.split() == [b'45', b'-1', b'true', b'true']
    assert b'45 radians is more than a whole turn' in left.stderr
