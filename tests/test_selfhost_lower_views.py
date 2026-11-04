"""Borrowed views and collection eligibility match their frozen traversal."""
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_selfhost_lower_analysis import DRIVER


MAIN = r'''main = ():
    lower_test_cli()
    opt_release = true; dbg_on = false; copies_on = false
    t = mk_tuple([T_STR, T_INT])
    root = la_local(t, LF_PARAM); r = int(nodes[root].sym)
    candidate = la_local(t); c = int(nodes[candidate].sym)
    decl = la_node(.vardecl, 0, root); nodes[decl].sym = i32(c)
    body = la_node(.block, 0, 0, [decl])
    f = la_fn(body); fns[f].params = [r]; fns[f].locals = [c]
    cur_fn = f; locals[r].owner = i32(f)
    assert(hv_root(r) and plain_read(root))
    find_views(f)
    assert(held_views.contains(c) and hv_part(candidate))
    assert(int(locals[c].flags) & LF_HELDVIEW != 0)
    assert(held_opt_reg(candidate) == -1)
    # A repeated pass clears the old view flags; a lambda prevents borrowing.
    fns[f].body = i32(la_node(.block, 0, 0, [decl, la_node(.lambda)]))
    find_views(f); assert(held_views.len() == 0 and int(locals[c].flags) & LF_HELDVIEW == 0)
    # Synthetic parameter bindings share the source's slot without owning it.
    nodes[decl].aux2 = 1
    locals[r].vreg = 21; locals[r].offset = 24
    assert(param_view_decl(decl, c) and locals[c].vreg == 21 and locals[c].offset == 24)
    locals[c].flags = i32(LF_ASSIGNED)
    assert(not param_view_decl(decl, c))
    arr = mk_array(T_INT); g = la_global("rows", arr); gi = int(nodes[g].sym)
    one = la_node(.int_lit, 0, 0, [], T_INT); nodes[one].ival = 1
    at = la_node(.index, g, one, [], T_INT)
    assert(plain_read(at) and not plain_read(la_node(.call)))
    uniq_globals.resize(globals.len()); uniq_globals[gi] = true
    ug_scan(at, 1); assert(is_uniq_array(g))
    ug_scan(g, 0); assert(not is_uniq_array(g))
    uniq_globals[gi] = true
    push = la_node(.intrinsic, 0, 0, [g, one]); nodes[push].aux = i32(int(IN.push))
    ug_scan(push, 1); assert(is_uniq_array(g))
    ug_scan(push, -1); assert(not is_uniq_array(g))
    key = lpath_key(g)
    fixed_paths = [FixedPath(key, 12, 13, -1)]
    assert(fixed_path_of(g) == 0 and fixed_path_of(one) == -1)
    fp_end(1); assert(fixed_paths.len() == 0)
    uniq_locals = [r, c]; uq_end(1); assert(uniq_locals == [r])
    scope_locals = [[c]]; assert(declared_in_scope(c) and not declared_in_scope(r))
    assert(comprehension_value(one) and not comprehension_value(body))
    assert(simple_cond(la_node(.bool_lit)) and not simple_cond(la_node(.call)))
    assert(bounded_open_for(la_node(.for_)) == 0)
    print("ok")
'''


def test_lower_views_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    driver = "use 'ir.jo'\nuse 'copies.jo'\nuse 'lower_analysis.dewy'\n" + DRIVER + MAIN
    out = compare_leaf(compiler, tmp_path, False, driver,
                       extra_stems=('lower_views',),
                       jo_doubles=modules_for(source, output, 'lower_views'))
    assert out.endswith(b'ok\n')
