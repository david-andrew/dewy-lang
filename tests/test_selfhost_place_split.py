"""Splitting methods that lend a place: routes, guards and diagnostics match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
const NF_AT = 2147483648
const NF_GENERIC = 64
const NF_VOID = 4194304
const NF_INDEX_CAPTURED = 1024
const NF_WRITTEN_VOID = NF_INDEX_CAPTURED
struct PlaceMethod:
    route: int[]
    written: int = 0
    fails: bool = false
    guards: int = 0
    release: int = 0
    at: int = 0
nodes: Node[] = [Node()]
lists: i32[]
names: str[] = [""]
dewy_param_kinds: {int: int[]} = {}
place_methods: {int: PlaceMethod}
place_written: {int: int}
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
nkids = (n: int) -> int: int(nodes[n].nlist)
kid_c = (n: int) -> int: if nodes[n].kind == .for_: 0 else: int(nodes[n].c)
kid_d = (n: int) -> int: int(nodes[n].d)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
set_list2 = (n: int, items: int[]): node_set_list2(mut nodes, mut lists, n, items)
clone = (n: int) -> int:
    nodes.push(nodes[n])
    nodes.len() - 1
fatal = (pos: int, msg: str) -> never:
    print("fatal {pos}: {msg}")
    exit(41)
intern = (text: str) -> int:
    i = names.index_of(text)
    if i >= 0: return i
    names.push(text)
    names.len() - 1
name_of = (n: int) -> str: names[n]
bc_bool = (b: bool, pos: int) -> int: mk(.bool_lit, pos)
bc_block = (items: int[], pos: int) -> int:
    n = mk(.block, pos)
    set_list(n, items)
    n
dw_finish_function = (n: int, parameters: int[], body: int, name: str) -> int:
    print("finish {n} {parameters} {body} {name}")
    n
place_names_used = (n: int, used: {int: bool}) -> int:
    if n == 0: return 0
    if nodes[n].kind == .ident and used.has(int(nodes[n].name)): return n
    loop c in kids(n):
        at = place_names_used(c, used)
        if at != 0: return at
    place_names_used(int(nodes[n].a), used)
'''

DRIVER = r'''
ident = (name: str, pos: int = 0) -> int:
    n = mk(.ident, pos); nodes[n].name = i32(intern(name)); n
at_flag = (n: int) -> int:
    add_flag(n, int(NF_AT)); n
field = (a: int, name: str, pos: int = 0) -> int:
    n = mk(.field, pos); nodes[n].a = i32(a); nodes[n].name = i32(intern(name)); n
index = (a: int) -> int:
    n = mk(.index, 0); nodes[n].a = i32(a); n
gives = (place: int, pos: int = 40) -> int:
    n = mk(.return_, pos); nodes[n].a = i32(place); n
value = (pos: int = 41) -> int:
    n = mk(.return_, pos); nodes[n].a = i32(mk(.int_lit, pos)); n
stmt = (e: int) -> int:
    n = mk(.exprstmt, 42); nodes[n].a = i32(e); n
local = (name: str, sub: int[] = []) -> int:
    n = mk(.vardecl, 43); nodes[n].name = i32(intern(name)); set_list(n, sub); n
param_bind = (name: str) -> int:
    n = local(name); nodes[n].aux2 = 1; n
function = (statements: int[], written: int = 0) -> int:
    f = mk(.fn_, 44)
    nodes[f].name = i32(intern("lend"))
    b = mk(.block, 45); set_list(b, statements)
    nodes[f].b = i32(b)
    if written != 0: place_written[f] = written
    f
route = (n: int) -> str: "{place_route_of(n, self)}"
self = 0
report = (f: int, out: int[]):
    print("out {out} body {kids(int(nodes[f].b))}")
    loop x in out + [f]:
        if let p = place_methods.get(x):
            print("{x}: {p.route} {p.written} {p.fails} {p.guards} {names[p.release]} {p.at}")
        print("{names[int(nodes[x].name)]} {nodes[x].flags} {kids(int(nodes[x].b))} {nodes[x].b}")
    loop i in [0..nodes.len()):
        k = nodes[i].kind
        if k == .record_lit or k == .namedarg or k == .tname or k == .param: print("{i} {nodes[i].name} {nodes[i].a} {kids(i)}")
self_at = () -> int: ident("self")
receiver_name = () -> int: intern("self")
split = (what: str, f: int):
    print("== {what}")
    report(f, place_method_split(f, receiver_name(), "lend"))
main = ():
    self = receiver_name()
    # Routes and given places.
    print(route(field(field(self_at(), "a"), "b")))
    print(route(self_at()))
    print(route(field(ident("other"), "a")))
    print(place_given(0, self))
    print(place_given(field(self_at(), "a"), self))
    print(place_given(at_flag(index(field(self_at(), "a"))), self))
    print(place_given(at_flag(ident("other")), self))
    # Returns: lambdas and functions hide theirs; each child slot is searched.
    places: int[]
    values: int[]
    good = at_flag(field(self_at(), "balance"))
    tree = mk(.if_, 1)
    nodes[tree].a = i32(gives(good)); nodes[tree].b = i32(value()); nodes[tree].c = i32(value()); nodes[tree].d = i32(value())
    hidden = mk(.lambda, 2); nodes[hidden].a = i32(value())
    set_list(tree, [hidden, mk(.fn_, 3), value()])
    place_returns_in(tree, self, places, values)
    print("{places} {values}")
    loop_body = mk(.for_, 4); nodes[loop_body].c = i32(value())
    empty: int[]
    place_returns_in(loop_body, self, empty, values)
    print("{empty} {values}")
    # A method: no body, no place, misplaced places, no field; then each shape that splits.
    case = if args().len() > 1: args()[1] else: ""
    typed = mk(.tname, 46)
    bare = mk(.fn_, 47); nodes[bare].name = i32(intern("bare"))
    bare2 = mk(.fn_, 48); nodes[bare2].b = i32(mk(.int_lit, 49))
    place_written[bare2] = typed
    if case == "": split("no body", bare)
    if case == "value body written": split(case, bare2)
    if case == "": split("no place", function([value()]))
    if case == "no place written": split(case, function([value()], typed))
    if case == "two places": split(case, function([gives(good, 50), gives(good, 51)]))
    if case == "place first": split(case, function([gives(good, 52), local("x")]))
    if case == "element": split(case, function([gives(at_flag(index(field(self_at(), "items"))), 53)]))
    if case == "": split("expression", function([stmt(good)]))
    if case == "": split("return", function([gives(good)], typed))
    if case == "": split("params", function([param_bind("p"), param_bind("q"), local("n"), gives(good)]))
    if case == "": split("guards", function([local("a"), local("skipped", [mk(.int_lit, 54)]), local("b"), gives(good)]))
    fails = function([param_bind("p"), mk(.if_, 55), local("held"), gives(good)])
    nodes[kids(int(nodes[fails].b))[1]].b = i32(value())
    dewy_param_kinds[fails] = [1, 2]
    if case == "": split("fails", fails)
    fails2 = function([mk(.if_, 56), gives(good)])
    nodes[kids(int(nodes[fails2].b))[0]].b = i32(value())
    if case == "": split("fails without guards", fails2)
    used = function([local("early"), mk(.if_, 57), stmt(ident("early", 58)), gives(good)])
    nodes[kids(int(nodes[used].b))[1]].b = i32(value())
    if case == "early used": split(case, used)
    print("split ok")
'''


FATAL = ('value body written', 'no place written', 'two places', 'place first', 'element', 'early used')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_place_split_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'place_split'), DRIVER,
                             doubles={'services.jo': SERVICES}, services=('ast', 'expr', 'util', 'dewy_nodes', 'place_methods'),
                             invocations=[((), 0)] + [((case,), 41) for case in FATAL])
    assert outputs[0].endswith(b'split ok\n') and b'lend$acquire' in outputs[0] and b'lend$release' in outputs[0]
    for output, text in zip(outputs[1:], (b'and its body gives a value', b'and its body gives none', b'as its last statement',
                                          b'as its last statement', b'not an element', b'is declared before')):
        assert text in output, (text, output[-300:])
