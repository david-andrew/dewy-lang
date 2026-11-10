"""Alias, write, resize and path summaries preserve their frozen behavior."""
import re

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''use 'main.jo'
use 'ast.jo'
use "node_store.dewy"
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'util.jo'
use 'expr.jo'
use 'lower.jo'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
la_node = (k: NK, a: int = 0, b: int = 0, xs: int[] = [], t: int = 0) -> int:
    n = mk(k, 0)
    nodes[n].a = i32(a); nodes[n].b = i32(b); nodes[n].type = i32(t)
    nodes[n].list = i32(lists.len()); nodes[n].nlist = i32(xs.len())
    loop x in xs: lists.push(i32(x))
    n
la_global = (name: str, t: int) -> int:
    g = globals.len(); globals.push(Global(name=i32(intern(name)), type=i32(t), fn_written=true))
    n = la_node(.ident, 0, 0, [], t)
    nodes[n].aux = i32(int(SK.global)); nodes[n].sym = i32(g); nodes[n].name = i32(intern(name)); n
la_local = (t: int, flags: int = 0, alias: int = 0) -> int:
    l = locals.len(); locals.push(Local(type=i32(t), flags=i32(flags), alias=i32(alias)))
    n = la_node(.ident, 0, 0, [], t)
    nodes[n].aux = i32(int(SK.local)); nodes[n].sym = i32(l); n
la_fn = (body: int) -> int:
    f = fns.len(); fns.push(FnInst(body=i32(body))); f
la_call = (f: int) -> int:
    n = la_node(.call); nodes[n].sym = i32(f); n
la_clear = ():
    fw_direct.clear(); fw_total.clear(); fw_named.clear(); fr_direct.clear(); fr_total.clear()
'''

MAIN = r'''main = ():
    lower_test_cli()
    la_clear()
    arr = mk_array(T_INT)
    g = la_global("g", arr); h = la_global("h", arr)
    gi = int(nodes[g].sym); hi = int(nodes[h].sym)
    one = la_node(.int_lit, 0, 0, [], T_INT); nodes[one].ival = 1
    two = la_node(.int_lit, 0, 0, [], T_INT); nodes[two].ival = 2
    at = la_node(.index, g, one, [], T_INT)
    other = la_node(.index, g, two, [], T_INT)
    assert(place_var(at) == g and pw_heap and pw_depth == 1)
    assert(elem_root(at) == g and place_text(at) == "g[1]")
    assert(not steps_overlap(place_steps(at), place_steps(other)))
    nested = la_node(.index, at, two, [], T_INT)
    steps = place_steps(nested); assert(steps.len() == 2 and steps[0] == at and steps[1] == nested)
    local = la_local(arr)
    alias = la_local(arr, LF_ALIAS, local)
    assert(place_var(alias) == local and not pw_heap)
    assert(mut_plain_root(local) and same_var(local, local) and not same_var(local, g))
    assert(shares_mut_root(at, [g], 1) and not shares_mut_root(at, [h], 1))
    assert(mut_may_reach(at, [g], 1) and not mut_may_reach(local, [h], 1))
    assert(mentions_var(nested, g) and mentions_local(alias, int(nodes[alias].sym)))
    key = lpath_key(g); child = lpath_intern(key, 7)
    assert(lpath_key(g) == key and path_within(child, key) and not path_within(key, child))
    assert(lpath_root(g) == g and lpath_key(at) == 0)
    write = la_node(.assign, g, h)
    assert(write_root(at) == g and write_overlaps(at, g, 0))
    assert(may_write_root(write, g) and not may_write_root(write, local))
    assert(not unchanged_by(g, write) and unchanged_by(local, write))
    assert(assign_rhs_effects(write) and not has_call(write) and index_stable(one, write))
    nodes[write].pos = 123
    assert(lm_change_at(write, key) == 123)
    leaf = la_fn(write); caller = la_fn(la_call(leaf))
    w = fn_writes(caller)
    assert(not w.all and w.globals == [gi] and w.mentions.contains(gi) and w.mentions.contains(hi))
    assert(fn_writes_named(caller).globals == [gi] and fn_resizes(caller) == [gi])
    assert(fn_writes(caller).globals == [gi] and fn_resizes(caller) == [gi])
    call = la_call(caller)
    assert(has_call(call) and may_write_root(call, g) and not calls_leave(call, g, false))
    assert(calls_leave(call, h, false) and not calls_leave(call, h, true))
    assert(lm_resizing_call(call, gi) == call and lm_resizing_call(call, hi) == 0)
    assert(copy_through(at, 0) and not copy_through(local, caller))
    assert(borrow_may_change(at, [], 0, 0) and not borrow_may_change(local, [], 0, caller))
    # Nested function bodies are excluded; unknown calls fail closed.
    hidden = la_node(.lambda, write)
    assert(not may_write_root(hidden, g) and calls_leave(hidden, g, true))
    assert(fn_writes(la_fn(hidden)).globals.len() == 0)
    opaque = la_node(.call); nodes[opaque].aux = 1
    unknown = la_fn(opaque)
    assert(fn_writes(unknown).all and not fn_writes_named(unknown).all)
    # Named cycles terminate and include writes and resizes beyond a back edge.
    back = la_call(caller)
    fns[leaf].body = i32(la_node(.block, 0, 0, [back, write])); la_clear()
    assert(fn_writes(caller).globals == [gi] and fn_resizes(caller) == [gi])
    # Mutation intrinsics contribute to the same summaries.
    push = la_node(.intrinsic, 0, 0, [g, one]); nodes[push].aux = i32(int(IN.push))
    nodes[push].pos = 124
    assert(may_write_root(push, g) and lm_change_at(push, key) == 124)
    assert(fn_resizes(la_fn(push)) == [gi])
    print("ok")
'''


def test_lower_analysis_twins(compiler, tmp_path, monkeypatch):
    from tests.support import ROOT
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    out = compare_leaf(compiler, tmp_path, False, DRIVER + MAIN,
                       extra_stems=('lower_analysis',),
                       jo_doubles=modules_for(source, output, 'lower_analysis'))
    assert out.endswith(b'ok\n')


def test_lower_analysis_alias_error(compiler, tmp_path, monkeypatch):
    from tests.support import ROOT
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output, 'lower_analysis')
    diagnostic_status(modules, 'fatal')
    driver = DRIVER + r'''main = ():
    lower_test_cli()
    g = la_global("g", mk_array(T_INT))
    one = la_node(.int_lit, 0, 0, [], T_INT); nodes[one].ival = 1
    at = la_node(.index, g, one, [], T_INT)
    mut_alias_check([at, g], 1, 0)
    print("unreachable")
'''
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_analysis',), jo_doubles=modules)
    assert b'g[1] is passed as' in out
    assert b"cannot also hold or change 'g'" in out
    assert b'unreachable' not in out
