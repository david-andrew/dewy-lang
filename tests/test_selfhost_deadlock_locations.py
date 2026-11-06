"""Demanded lock identity follows aliases, captures, constructors and call arguments."""
import re

import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER

JO = jo_doubles({
    'deadlock.jo': {
        'DlLoc': '''struct DlLoc:
    root: int
    id: int
    k: int
    route: str
    exact: bool''',
        'DlEdge': '''struct DlEdge:
    held: DlLoc
    taken: DlLoc
    held_site: int
    taken_site: int
    via: str
    at: int = 0''',
        'dl_param_index': 'dl_param_index: {int: int}',
        'dl_inits': 'dl_inits: {int: int}',
        'dc_split': 'dc_split = (n: int) -> bool: n != 0 and n == split_node',
    },
    'ast.jo': {
        'node_store': "use 'node_store.dewy'",
        'nodes': 'nodes: Node[] = [Node()]',
        'lists': 'lists: i32[]',
        'nkids': 'nkids = (n: int) -> int: int(nodes[n].nlist)',
        'kid': 'kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])',
    },
    'check.jo': {
        'checker_state': "use 'checker_state.dewy'",
        'lib_dir': 'lib_dir = "/library"',
        'globals': 'globals: Global[]',
        'locals': 'locals: Local[]',
        'fns': 'fns: FnInst[]',
        'LF_ASSIGNED': 'const LF_ASSIGNED = 16',
        'LF_ALIAS': 'const LF_ALIAS = 8',
        'LF_CAPTURE': 'const LF_CAPTURE = 4',
    },
    'util.jo': {
        'source_types': "use 'source_types.dewy'",
        'files': 'files: SrcFile[]',
        'name_of': 'name_of = (n: int) -> str: names[n]',
        'pos_file': 'pos_file = (p: int) -> int: p',
        'line_col': 'line_col = (p: int) -> (int, int): (p + 10, 2)',
    },
    'directives.jo': {'dir_deadlocks_any': 'dir_deadlocks_any = false'},
})
# The frozen body's unused imports remain leaf-local test services.
for module in ('types', 'expr', 'lower', 'isolation', 'concurrency', 'effects',
               'prelude', 'errors', 'ownership'):
    JO.setdefault(module + '.jo', "use 'driver.jo'\n")
for stem in ('effect_lattice', 'effect_types', 'lower_helpers', 'lower_races', 'effect_contracts', 'effect_control',
             'isolation_ops', 'concurrency_types', 'concurrency_tasks'):
    JO[stem + '.dewy'] = ''
    JO[stem + '.jo'] = ''

JO['deadlock_channels.dewy'] = 'from p"deadlock.jo" import (dc_split as split_double)\ndc_split=(n:int64):>bool=>split_double(n)\n'
JO['deadlock_channels.jo'] = "use 'deadlock.jo'\n"

DRIVER = r'''
use 'deadlock.jo'
use 'ast.jo'
use 'check.jo'
use 'util.jo'
use 'directives.jo'
names = ["", "alpha", "beta", "$hidden", "mutex", "channel", "mpmc", "spsc", "atomic", "field"]
split_node = 0
node = (k: NK, a: int = 0, sym: int = 0, aux: int = 0) -> int:
    n = nodes.len(); nodes.push(Node(kind=k, a=i32(a), sym=i32(sym), aux=i32(aux))); n
children = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
local = (l: int) -> int: node(.ident, 0, l, int(SK.local))
main = ():
    globals.resize(2); locals.resize(8); fns.resize(2); files.resize(6)
    globals[1].name = 1; locals[1].name = 1; locals[2].name = 2; locals[2].owner = 1
    locals[6].name = 3
    fns[1].params = [2]
    g = node(.ident, 0, 1, int(SK.global))
    assert(dl_key(dl_unknown()) == "0:0:0" and dl_lib() == "/library/prelude/locks.dewy")
    global = dl_resolve(g, 1)
    assert(global.root == 1 and global.id == 1 and global.exact)
    assert(dl_name(global) == "'alpha'" and dl_line(4) == "line 14")
    assert(dl_resolve(node(.int_lit), 1).root == 0 and dl_resolve(0, 1).root == 0)
    assert(dl_resolve(g, 1, 33).root == 0)
    wrapped = node(.conv, node(.addr, node(.narrow, g)))
    assert(dl_must(global, dl_resolve(wrapped, 1)))
    field = node(.field, g); nodes[field].name = 9
    loc = dl_resolve(node(.index, field), 1)
    assert(loc.route == ".field[]" and not loc.exact)
    assert(dl_may(loc, loc) and not dl_must(loc, loc) and not dl_named(loc))
    assert(not dl_may(dl_unknown(), dl_unknown()) and not dl_must(global, loc))
    assert(dl_name(dl_resolve(local(6), 1)) == "'a lock'")
    assert(dl_name(DlLoc(3, 1, 99, "", true)) == "'a lock'")
    assert(dl_resolve(local(1), 1).root == 4)
    dl_param_index[2] = 0
    param = dl_resolve(local(2), 1)
    assert(dl_symbolic(param) and dl_named(param) and dl_name(param) == "'beta'")
    locals[3].flags = LF_CAPTURE; locals[3].outer = 2
    assert(dl_must(param, dl_resolve(local(3), 1)))
    locals[4].flags = LF_ALIAS; locals[4].alias = i32(g)
    assert(dl_must(global, dl_resolve(local(4), 1)))
    locals[5].flags = LF_CAPTURE
    assert(dl_resolve(local(5), 1).root == 0)
    locals[4].flags |= LF_ASSIGNED
    assert(not dl_resolve(local(4), 1).exact)
    decl = node(.vardecl); nodes[decl].name = 2; nodes[decl].b = i32(g); dl_inits[1] = decl
    assert(dl_must(global, dl_resolve(local(1), 1)))
    nodes[decl].b = i32(node(.int_lit))
    assert(dl_named(dl_resolve(local(1), 1)) and dl_name(dl_resolve(local(1), 1)) == "'beta'")
    split_node = node(.call); children(split_node, [g]); nodes[decl].b = i32(split_node)
    assert(dl_must(global, dl_resolve(local(1), 1)))
    children(split_node, [node(.int_lit)])
    assert(dl_resolve(local(1), 1).root == 2)
    split_node = 0
    call = node(.call, 0, 1); nodes[decl].b = i32(call)
    dir_deadlocks_any = true
    assert(dl_resolve(local(1), 1).root == 0)
    paths = ["/library/prelude/locks.dewy", "/library/prelude/channels.dewy", "/library/prelude/mpmc.dewy", "/library/prelude/spsc.dewy", "/library/std/thread.jo"]
    loop i in [0..5):
        fn = node(.fn_); nodes[fn].name = i32(4 + i); nodes[fn].pos = i + 1
        files[i + 1].path = paths[i]; fns[1].decl = i32(fn)
        assert(dl_makes_handle(call) and dl_resolve(local(1), 1).root == 2)
        gd = node(.vardecl); nodes[gd].b = i32(node(.conv, call)); globals[1].decl = i32(gd)
        assert(dl_named(global))
        files[i + 1].path = "/other"; assert(not dl_makes_handle(call) and not dl_named(global))
    assert(not dl_named(DlLoc(4, 1, 0, "", true)))
    assert(not dl_named(DlLoc(2, decl, 0, "", false)))
    nodes[call].aux = 1; assert(not dl_makes_handle(call)); nodes[call].aux = 0
    nodes[call].sym = 0; assert(not dl_makes_handle(call)); nodes[call].sym = 1
    fns[1].decl = 0; assert(not dl_makes_handle(call))
    assert(dl_receiver(call) == 0)
    arg = node(.namedarg, g); children(call, [arg]); assert(dl_receiver(call) == arg)
    substituted = dl_subst(dl_extend(param, ".field", true), 1, call, 2)
    assert(substituted.root == 1 and substituted.route == ".field" and substituted.exact)
    assert(dl_subst(param, 1, 0, 2).root == 0)
    assert(dl_must(param, dl_subst(param, 9, call, 2)))
    assert(dl_must(global, dl_subst(global, 1, call, 2)))
    children(call, [node(.int_lit)]); assert(dl_subst(param, 1, call, 2).root == 0)
    e = DlEdge(global, param, 3, 4, "callback")
    assert(dl_path(e) == "takes 'alpha' (line 13) and then 'beta' (line 14) (in callback)")
    e.via = ""; assert(dl_path(e) == "takes 'alpha' (line 13) and then 'beta' (line 14)")
    print("locations ok")
'''

base = RESOLVER.split('node = (kind:')[0]
base = re.sub(r'(?m)^(?:nodes|lists|names|files)\s*[:=][^\n]*\n', '', base)
names = re.search(r'(?m)^names = [^\n]*\n', DRIVER)
JO['util.jo'] += names[0]
DRIVER = base + DRIVER[:names.start()] + DRIVER[names.end():]

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_deadlock_locations_twins(compiler, tmp_path, release):
    assert compare_leaf(compiler, tmp_path, release, DRIVER,
                        extra_stems=('deadlock_locations',), jo_doubles=JO) == b'locations ok\n'
