"""Effect site indexes and result walks preserve demand, growth and invalidation."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

DRIVER = r'''
use 'main.jo'
use 'effects.jo'
use 'types.jo'
use 'ast.jo'
use 'check.jo'
use "checker_state.dewy"
use "node_store.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    locals.resize(4)
    fns.resize(4)
    effect_final = false
    read = mk(.ident, 0)
    nodes[read].aux = i32(int(SK.local))
    nodes[read].sym = 1
    nodes[read].type = i32(T_INT)
    decl = mk(.vardecl, 0)
    nodes[decl].sym = 1
    call = mk(.call, 0)
    nodes[call].sym = 2
    write = mk(.assign, 0)
    nodes[write].a = i32(read)
    # Ask uses first, then a previously undemanded write kind.
    assert(effect_use_sites(2) == [call])
    assert(effect_write_sites(1) == [decl, write])
    assert(effect_scalar_sites(1) == [decl, write])
    assert(effect_use_sites(3).len() == 0)
    effect_final = true
    assert(effect_use_sites(2) == [call])
    assert(effect_write_sites(1) == [decl, write])
    assert(effect_scalar_sites(1) == [decl, write])
    assert(effect_sites(0, 0) == [read, decl, call, write])
    # Grow after all three indexes exist; query in a different order.
    ref = mk(.fnref, 0)
    nodes[ref].sym = 2
    later = mk(.vardecl, 0)
    nodes[later].sym = 1
    assert(effect_scalar_sites(1) == [decl, write, later])
    assert(effect_use_sites(2) == [call, ref])
    assert(effect_write_sites(1) == [decl, write, later])
    assert(effect_use_sites(2) == [call, ref])
    # Preparation can rewrite a node without changing the arena length.
    nodes[call].sym = 3
    nodes[later].sym = 2
    effect_ix_nodes = 0
    effect_ix_locals = 0
    assert(effect_write_sites(2) == [later])
    assert(effect_use_sites(2) == [ref])
    assert(effect_use_sites(3) == [call])
    assert(effect_scalar_sites(1) == [decl, write])
    # A graph reset must not retain a chain from the preceding graph.
    effects_reset()
    effect_final = true
    assert(effect_use_sites(2) == [ref])
    assert(effect_write_sites(1) == [decl, write])
    assert(effect_site_key(0, read) == 0 and effect_write_root(write) == 1)
    global_decl = mk(.vardecl, 0)
    nodes[global_decl].sym = 3; add_flag(global_decl, NF_GLOBAL)
    assert(effect_site_key(0, global_decl) == 0)
    leaf = mk(.int_lit, 0)
    ret = mk(.return_, 0); nodes[ret].a = i32(leaf)
    block = mk(.block, 0); set_list(block, [ret])
    returns: int[]
    effect_returns(block, returns)
    assert(returns == [leaf])
    print("sites ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_sites_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_sites')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_sites',), jo_doubles=modules)
    assert out == b'sites ok\n'
