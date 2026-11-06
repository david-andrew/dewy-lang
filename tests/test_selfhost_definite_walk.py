"""Definite assignment walks agree with frozen Jo over hand-built checked trees."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER

STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/definite.jo').read_text())

JO = jo_doubles({
    'ast.jo': {
        'node_store': "use 'node_store.dewy'",
        'nodes': 'nodes: Node[] = [Node()]',
        'lists': 'lists: i32[]',
        'NF_GENERIC': 'const NF_GENERIC = 64',
        'has_flag': 'has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0',
        'kids': 'kids = (n: int) -> int[]: node_kids(nodes, lists, n)',
        'kids2': 'kids2 = (n: int) -> int[]: node_kids2(nodes, lists, n)',
    },
    'check.jo': {
        'checker_state': "use 'checker_state.dewy'",
        'ast': "use 'ast.jo'",
        'globals': 'globals: Global[]',
        'locals': 'locals: Local[]',
        'fns': 'fns: FnInst[]',
        'LF_CAPTURE': 'const LF_CAPTURE = 4',
        'stmt_terminates': 'stmt_terminates = (s: int) -> bool: nodes[s].kind == .return_ and nodes[s].aux == 9',
    },
    'util.jo': {
        'err_notes': 'err_notes: (int, str)[]',
        'name_of': 'name_of = (n: int) -> str: "name{n}"',
        'fatal': 'fatal = (pos: int, msg: str): events.push("fatal:{pos}:{msg}")',
    },
    'types.jo': {'dt': 'dt = (t: int) -> str: "type{t}"'},
})
JO['definite.jo'] = "use 'checker_state.dewy'\n" + STATE
JO['isolation.jo'] = r'''use 'node_store.dewy'
isolation_children = (k: NK) -> int:
    if k == .tuple: return 16
    if k == .field: return 1
    if k == .cast: return 2
    if k == .if_: return 7
    if k == .map_lit: return 32
    -1
'''

DRIVER = RESOLVER.split('node = (kind:')[0]
DRIVER = re.sub(r'(?m)^(?:nodes|lists)\s*[:=][^\n]*\n', '', DRIVER) + r'''
use 'definite.jo'
use 'ast.jo'
use 'check.jo'
use 'util.jo'
use 'types.jo'
ASSIGN = i32(int(Tok.assign))
PLUS = i32(int(Tok.pluseq))
node = (k: NK, a: int = 0, b: int = 0, c: int = 0, sym: int = 0, aux: int = 0, pos: int = 0) -> int:
    n = nodes.len()
    nodes.push(Node(kind=k, a=i32(a), b=i32(b), c=i32(c), sym=i32(sym), aux=i32(aux), pos=pos))
    n
list = (k: NK, items: int[], a: int = 0, b: int = 0) -> int:
    n = node(k, a, b)
    node_set_list(mut nodes, mut lists, n, items)
    n
lit = () -> int: node(.int_lit)
at = 100
read = (l: int) -> int:
    at += 1
    node(.ident, 0, 0, 0, l, int(SK.local), at)
gread = (g: int) -> int:
    at += 1
    node(.ident, 0, 0, 0, g, int(SK.global), at)
give = (target: int, value: int = 0) -> int:
    n = node(.assign, target, if value == 0: lit() else: value)
    nodes[n].op = ASSIGN
    n
gets = (l: int, value: int = 0) -> int: give(read(l), value)
ggets = (g: int, value: int = 0) -> int: give(gread(g), value)
decl = (l: int, init: int = 0) -> int:
    d = node(.vardecl, 0, init, 0, l)
    da_record(d)
    d
out = () -> int: node(.return_)
jump = (k: NK, name: int = 0) -> int:
    n = node(k)
    nodes[n].name = i32(name)
    n
show = (what: str, st: DaState): print("{what}: {st.unset} {st.done}")
flush = (what: str):
    print("== {what}")
    loop e in events: print(e)
    loop note in err_notes: print("{note.0}:{note.1}")
    events = []
    err_notes = []
    da_names = {}
# One function: its unset local 1 must be given a value on every path before the final read.
check = (what: str, l: int, statements: int[]):
    items = [decl(l)]
    loop s in statements: items.push(s)
    items.push(read(l))
    da_check_fn(list(.block, items), 0)
    assert(da_decls.len() == 0, "the checked function's records are dropped")
    flush(what)
fn = (body: int) -> int:
    f = fns.len()
    fns.push(FnInst(body=i32(body)))
    f
call = (f: int, args: int[] = []) -> int:
    n = list(.call, args)
    nodes[n].sym = i32(f)
    n
reset = ():
    dg_summaries = {}
    dg_progress = {}
    dg_mention_memo = {}
    dg_active = false
    dg_exits = false
    dg_collecting = false
    dg_sink = []
    dg_exit_states = []
program = (what: str, inits: int[], main_fn: int, later: int[]):
    reset()
    dg_check_program(inits, main_fn, later)
    assert(not dg_active, "the walk ends inactive")
    flush(what)
main = ():
    locals.resize(12)
    loop i in [0..12):
        locals[i].name = i32(i)
        locals[i].type = i32(i + 40)
        locals[i].pos = 1000 + i
    globals.resize(6)
    loop i in [0..6):
        globals[i].name = i32(i + 20)
        globals[i].decl = i32(if i == 5: 0 else: lit())
    fns.resize(1)
    # States join, keep their order and do not share what they were built from.
    a = DaState(unset=[1, 2])
    b = DaState(unset=[2, 3])
    show("join", da_join(a, b))
    show("left", a)
    show("done left", da_join(DaState(done=true), b))
    show("done right", da_join(a, DaState(done=true)))
    c = a
    da_remove(c, 1); da_remove(c, 9)
    show("removed", c)
    show("kept", a)
    # A capture stands for the variable it captures; a chain ends where it points to itself.
    locals[8].flags = i32(LF_CAPTURE); locals[8].outer = 7
    locals[7].flags = i32(LF_CAPTURE); locals[7].outer = 6
    locals[9].flags = i32(LF_CAPTURE); locals[9].outer = 9
    locals[10].flags = i32(LF_CAPTURE)
    loop l in [8, 7, 6, 9, 10]: print(da_root(l))
    # Locals, statement by statement.
    check("never given", 1, [])
    check("given", 1, [gets(1)])
    check("given after a use", 1, [read(1), gets(1)])
    check("read in its own value", 1, [gets(1, read(1))])
    check("captured given", 1, [gets(8)])
    check("captured read", 6, [read(8), gets(6)])
    plus = node(.assign, read(1), lit()); nodes[plus].op = PLUS
    check("compound", 1, [plus])
    tuple = list(.tuple, [read(1), list(.tuple, [read(2)]), node(.pwild)])
    check("unpacked", 1, [give(tuple)])
    nested = list(.tuple, [list(.tuple, [read(1)])])
    check("nested unpacked", 1, [give(nested)])
    check("other unpacked", 1, [give(list(.tuple, [read(3)]))])
    check("one branch", 1, [node(.if_, lit(), gets(1))])
    check("both branches", 1, [node(.if_, lit(), gets(1), gets(1))])
    check("iflet both", 1, [node(.iflet, lit(), gets(1), gets(1))])
    check("branch ends", 1, [node(.if_, lit(), out(), gets(1))])
    check("else ends", 1, [node(.if_, lit(), gets(1), out())])
    check("condition reads", 1, [node(.if_, read(1), gets(1), gets(1))])
    check("short circuit", 1, [node(.and_, lit(), gets(1))])
    check("short circuit left", 1, [node(.or_, gets(1), lit())])
    check("coalesce", 1, [node(.coalesce, lit(), read(1))])
    check("while", 1, [node(.while_, lit(), gets(1))])
    check("while reads", 1, [node(.while_, read(1), lit())])
    forever = () -> int:
        t = node(.bool_lit); nodes[t].ival = 1; t
    check("forever no break", 1, [node(.while_, forever(), list(.block, [gets(1)]))])
    check("forever break before", 1, [node(.while_, forever(), list(.block, [jump(.break_), gets(1)]))])
    check("forever break after", 1, [node(.while_, forever(), list(.block, [gets(1), jump(.break_)]))])
    check("forever two breaks", 1, [node(.while_, forever(), list(.block, [node(.if_, lit(), list(.block, [gets(1), jump(.break_)])), jump(.break_)]))])
    check("labelled break", 1, [node(.while_, forever(), list(.block, [node(.while_, forever(), list(.block, [jump(.break_, 3)])), gets(1), jump(.break_)]))])
    check("break outside", 1, [jump(.break_)])
    check("labelled outside", 1, [jump(.break_, 2)])
    check("for", 1, [node(.for_, lit(), gets(1))])
    check("for reads", 1, [node(.for_, read(1), lit())])
    check("for breaks", 1, [node(.for_, lit(), list(.block, [jump(.break_), jump(.break_, 2)]))])
    check("match empty", 1, [node(.match_, lit())])
    arm_given = gets(1)
    check("match arms", 1, [list(.match_, [arm_given, gets(1)], lit())])
    check("match one arm", 1, [list(.match_, [arm_given, lit()], read(2))])
    check("return", 1, [out()])
    check("return reads", 1, [node(.return_, read(1))])
    check("continue", 1, [jump(.continue_)])
    ended = node(.return_); nodes[ended].aux = 9
    check("terminated", 1, [ended, read(1)])
    check("in a block", 1, [list(.block, [gets(1)])])
    check("lambda reads", 1, [node(.lambda, 0, read(1))])
    check("lambda gives", 1, [node(.lambda, 0, gets(1))])
    check("declarations skip", 1, [node(.fn_, 0, read(1)), node(.defer_, read(1)), node(.typealias, read(1)), node(.struct_, read(1)), node(.enum_, read(1))])
    check("default kinds", 1, [node(.unary, read(1)), node(.index, lit(), read(1)), list(.tuple, [read(1)])])
    # A second declaration, with a value and without; a list declaration only walks its value.
    check("inner with value", 1, [decl(2, lit()), read(2), gets(1)])
    check("inner without", 1, [decl(2), read(2), gets(1)])
    inner = decl(2, read(1)); nodes[inner].nlist = 2
    check("list declaration", 1, [inner, read(2)])
    check("another declaration", 1, [gets(1), node(.vardecl, 0, lit(), 0, 1)])
    named = decl(3); nodes[named].a = i32(lit())
    check("named type", 3, [named])
    # (no records past the mark: nothing walked; a declaration with no local records no name)
    da_check_fn(read(1), 0)
    flush("nothing recorded")
    d0 = decl(0)
    da_check_fn(list(.block, [d0, read(0)]), 0)
    flush("no local")
    earlier = decl(1)
    da_check_fn(read(1), 1)
    assert(da_decls.len() == 1 and da_decls[0] == earlier, "records before the mark stay")
    da_decls = []
    flush("earlier records")
    # Globals: dg_record keeps one of each; nothing runs without one.
    program("no globals", [], 0, [])
    loop g in [1, 2, 1, 5]: dg_record(g)
    print(dg_globals)
    empty = fn(0)
    reads1 = fn(gread(1))
    gives1 = fn(ggets(1))
    gives_branch = fn(node(.if_, lit(), ggets(1)))
    gives_returns = fn(list(.block, [node(.if_, lit(), list(.block, [ggets(1), node(.return_)])), ggets(1)]))
    gives_returns_missing = fn(list(.block, [node(.if_, lit(), node(.return_)), ggets(1)]))
    gives_after_read = fn(list(.block, [gread(1), ggets(1)]))
    calls_reader = fn(call(reads1))
    recursive = fn(0); fns[recursive].body = i32(list(.block, [call(recursive), gread(2)]))
    mutual_a = fn(0); mutual_b = fn(0)
    fns[mutual_a].body = i32(list(.block, [call(mutual_b), gread(1)]))
    fns[mutual_b].body = i32(list(.block, [call(mutual_a), ggets(2)]))
    ending = fn(list(.block, [ggets(1), node(.return_)]))
    ending_early = fn(node(.return_))
    nop = fn(lit())
    # (each body stands behind every kind of mention and every child mask)
    mention = (n: int) -> int: fn(n)
    all = [1, 2, 5]
    give_all = (body: int[]) -> int:
        out_body = body
        loop g in all: out_body.push(ggets(g))
        fn(list(.block, out_body))
    program("all given", [give_all([])], 0, [])
    program("read at the top", [fn(gread(1))], 0, [])
    program("no-body and zero inits", [0, empty, give_all([])], 0, [])
    program("init ends", [ending_early, fn(gread(1))], 0, [])
    program("given in main", [], give_all([]), [])
    program("given, then read in main", [fn(list(.block, [ggets(1), ggets(2), ggets(5)]))], fn(list(.block, [gread(1), gread(2), gread(5)])), [])
    program("read in main", [], fn(gread(2)), [])
    program("unnamed global", [], fn(gread(5)), [])
    program("main ends", [], ending_early, [reads1, 0])
    program("main leaves one", [fn(list(.block, [ggets(2), ggets(5)]))], nop, [reads1, gives1, empty])
    program("main returns given", [fn(list(.block, [ggets(2), ggets(5)]))], ending, [reads1])
    program("main returns missing", [], fn(list(.block, [ggets(1), ggets(2), ggets(5), node(.if_, lit(), node(.return_))])), [reads1])
    # Calls: a read through a call, a function value, a partial, an escaping closure.
    given2 = fn(list(.block, [ggets(2), ggets(5)]))
    program("call reads", [given2], fn(list(.block, [call(reads1)])), [])
    program("transitive", [given2], fn(call(calls_reader)), [])
    program("call gives", [given2], fn(list(.block, [call(gives1), gread(1)])), [])
    program("call may give", [given2], fn(list(.block, [call(gives_branch), gread(1)])), [])
    program("returns all give", [given2], fn(list(.block, [call(gives_returns), gread(1)])), [])
    program("return may skip", [given2], fn(list(.block, [call(gives_returns_missing), gread(1)])), [])
    program("reads then gives", [given2], fn(call(gives_after_read)), [])
    program("recursion", [], fn(call(recursive)), [])
    program("mutual", [], fn(call(mutual_a)), [])
    program("no such call", [], fn(list(.block, [call(0), call(fns.len() + 5), call(-1)])), [])
    program("method call", [], fn(list(.call, [gread(1)])), [])
    aux_call = call(reads1); nodes[aux_call].aux = 1
    program("host call", [], fn(aux_call), [])
    fnref = node(.fnref); nodes[fnref].sym = i32(reads1)
    program("function value", [], fn(fnref), [])
    partial = node(.partial, gread(2)); nodes[partial].d = i32(reads1)
    program("partial", [], fn(partial), [])
    closure = node(.lambda, 0, gread(1)); nodes[closure].sym = i32(reads1)
    program("closure", [], fn(closure), [])
    generic = node(.lambda, 0, lit()); nodes[generic].sym = i32(reads1); nodes[generic].flags = 64
    program("generic closure", [], fn(generic), [])
    # dg_collect: what a body mentions, through each child mask and the call kinds.
    loop body in [list(.tuple, [gread(1)]), node(.field, gread(1)), node(.cast, 0, gread(1)), node(.if_, lit(), lit(), gread(1)), node(.unary, gread(1)), node(.index, lit(), gread(1)), list(.unary, [gread(1)]), node(.field, 0, gread(1))]:
        f = mention(body)
        program("mention", [], fn(call(f)), [])
        print(dg_mentions(f))
    second = node(.map_lit)
    node_set_list2(mut nodes, mut lists, second, [gread(1)])
    program("second list", [], fn(call(mention(second))), [])
    print(dg_mentions(fns.len() - 1))
    held = fn(call(reads1))
    made = node(.partial); nodes[made].d = i32(held)
    aref = node(.fnref); nodes[aref].sym = i32(held)
    lam = node(.lambda); nodes[lam].sym = i32(held)
    glam = node(.lambda); nodes[glam].sym = i32(held); nodes[glam].flags = 64
    acall = call(held); nodes[acall].aux = 1
    loop m in [made, aref, lam, glam, acall]:
        program("indirect mention", [], fn(call(mention(m))), [])
    print(dg_mentions(reads1))
    print(dg_summary(reads1).reads)
    print(dg_summaries.has(nop))
    print(dg_summary(nop).assigns)
    print("definite ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_definite_walk_twins(compiler, tmp_path, release):
    output = compare_leaf(compiler, tmp_path, release, DRIVER,
                          extra_stems=('definite_walk',), jo_doubles=JO)
    assert output.endswith(b'definite ok\n')
    for expected in (b'never given', b'unnamed global', b'is read before it is given a value on every path',
                     b'calls a function that reads', b'takes a function that reads',
                     b'makes a function that reads', b'declared here without a value'):
        assert expected in output, expected
