"""Dominating scalar guards: intervals, scopes, invalidation and word fits match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
const NF_U64 = 512
const T_INT = 1
const LF_MUTPARAM = 1
const LF_ALIAS = 2
const LF_CAPTURE = 4
const LF_CAPTURED = 8
const LF_SHARED = 16
const LF_ADDR = 32
const LF_BYREF = 64
const LF_EXPOSED = 128
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
cur_fn = 1
big_nodes: {int: bool} = {}
wide_nodes: {int: bool} = {}
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
ntype = (n: int) -> int: int(nodes[n].type)
exact_representation = (t: int) -> int: t
exact_has_node = (n: int) -> bool: big_nodes.has(n)
exact_bits = (n: int) -> int: if wide_nodes.has(n): 65 else: 64
integer_constant = (n: int) -> (bool, int):
    if nodes[n].kind == .int_lit: return (true, nodes[n].ival)
    (false, 0)
cx_token = (x: int) -> Tok: x as Tok
math_word_overflow = (op: int, a: int, b: int) -> bool:
    top = 9223372036854775807
    if op == 0:
        if b >= 0: return a > top - b
        return a < (-top - 1) - b
    if b >= 0: return a < (-top - 1) + b
    a > top + b
'''

DRIVER = r'''
use 'exact_guards.jo'
const BIG = 9223372036854775807
const SMALL = -9223372036854775807 - 1
fresh = (k: NK) -> int:
    nodes.push(Node(kind=k, pos=nodes.len()))
    nodes.len() - 1
local = (flags: int) -> int:
    locals.push(Local(flags=i32(flags)))
    locals.len() - 1
var = (l: int) -> int:
    n = fresh(.ident)
    nodes[n].aux = 1; nodes[n].sym = i32(l); nodes[n].type = 1
    n
lit = (v: int) -> int:
    n = fresh(.int_lit)
    nodes[n].ival = v
    n
bin = (op: Tok, a: int, b: int) -> int:
    n = fresh(.binary)
    nodes[n].op = i32(int(op)); nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
pair = (k: NK, a: int, b: int) -> int:
    n = fresh(k)
    nodes[n].a = i32(a); nodes[n].b = i32(b)
    n
bounds = (n: int): 
    a, b = eg_bound(n)
    print("  bound {n}: {a} {b}")
state = ():
    s = ""
    loop e in eg_stack: s = "{s} [{e.local} {e.lo} {e.hi} {e.owner} {e.version}]"
    print("  stack{s}")
    r = ""
    loop l in [0..eg_owner.len()): r = "{r} ({eg_lo[l]} {eg_hi[l]} {eg_owner[l]} {eg_version[l]})"
    print("  table{r}")
main = ():
    a = local(0); b = local(0); c = local(0)
    bare = fresh(.ident)
    wrong_sk = var(a); nodes[wrong_sk].aux = 2
    wrong_type = var(a); nodes[wrong_type].type = 2
    no_local = var(0)
    print("{eg_local(0)} {eg_local(-1)} {eg_local(bare)} {eg_local(wrong_sk)} {eg_local(wrong_type)} {eg_local(no_local)} {eg_local(var(c))}")
    loop f in [1, 2, 4, 8, 16, 32, 64, 128, 256]:
        print("flag {f}: {eg_local(var(local(f)))}")
    # Bounds before any table, then literals and unsigned literals.
    bounds(var(a))
    bounds(lit(7))
    u = lit(9); nodes[u].flags = 512
    bounds(u)
    # Not demanded: nothing learned; a function outside the table: nothing either.
    print(eg_begin(bin(.lt, var(a), lit(5)), true))
    state()
    eg_demanded = [false, true, false]
    cur_fn = 0
    print(eg_begin(bin(.lt, var(a), lit(5)), true))
    cur_fn = 2
    print(eg_begin(bin(.lt, var(a), lit(5)), true))
    cur_fn = 3
    print(eg_begin(bin(.lt, var(a), lit(5)), true))
    cur_fn = 1
    # Every comparison, both ways, at ordinary values and the extremes; each pushes or not.
    ops = [Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.eq, Tok.ne, Tok.plus]
    loop value in [5, -5, BIG, SMALL]:
        loop op in ops:
            loop yes in [true, false]:
                mark = eg_begin(bin(op, var(a), lit(value)), yes)
                print("{int(op)} {value} {yes} mark {mark}")
                state()
                bounds(var(a))
                eg_end(mark)
    state()
    # Conditions: negation, conjunction, disjunction, non-locals, non-constants, unsigned, aux.
    both = pair(.and_, bin(.gt, var(a), lit(1)), bin(.lt, var(b), lit(9)))
    either = pair(.or_, bin(.gt, var(a), lit(1)), bin(.lt, var(b), lit(9)))
    negated = fresh(.not_); nodes[negated].a = i32(either)
    aux = bin(.lt, var(a), lit(1)); nodes[aux].aux = 2
    ulit = lit(3); nodes[ulit].flags = 512
    loop cond in [both, either, negated, aux, bin(.lt, lit(1), lit(2)), bin(.lt, var(a), var(b)), bin(.lt, var(a), ulit), fresh(.call), 0]:
        loop yes in [true, false]:
            mark = eg_begin(cond, yes)
            print("cond {cond} {yes}")
            state()
            eg_end(mark)
    # The 64-term budget.
    deep = bin(.lt, var(a), lit(100))
    loop i in [0..80): deep = pair(.and_, bin(.gt, var(b), lit(i)), deep)
    mark = eg_begin(deep, true)
    print("deep {eg_stack.len() - mark}")
    bounds(var(b))
    eg_end(mark)
    # Nesting narrows; leaving restores; a write in the scope survives leaving.
    m1 = eg_begin(bin(.ge, var(a), lit(0)), true)
    m2 = eg_begin(bin(.le, var(a), lit(10)), true)
    bounds(var(a))
    m3 = eg_begin(bin(.ge, var(a), lit(-5)), true)
    bounds(var(a))
    eg_end(m3)
    eg_write(var(a))
    bounds(var(a))
    state()
    eg_end(m2)
    eg_end(m1)
    state()
    # Writes: a tuple target, a non-local, beyond the table, and with an empty stack.
    eg_write(var(c))
    state()
    m = eg_begin(bin(.ge, var(a), lit(1)), true)
    target = fresh(.tuple)
    node_set_list(mut nodes, mut lists, target, [var(a), var(b), lit(1)])
    eg_write(target)
    far = local(0)
    eg_write(var(far))
    state()
    eg_end(m)
    # A loop forgets what guards above it knew.
    m = eg_begin(pair(.and_, bin(.ge, var(a), lit(1)), bin(.ge, var(b), lit(2))), true)
    eg_loop()
    state()
    bounds(var(a))
    eg_end(m)
    state()
    # Other function: the same local's interval isn't this one's.
    m = eg_begin(bin(.ge, var(a), lit(1)), true)
    cur_fn = 2
    bounds(var(a))
    eg_demanded = [false, true, true]
    n2 = eg_begin(bin(.le, var(a), lit(4)), true)
    bounds(var(a))
    eg_end(n2)
    cur_fn = 1
    bounds(var(a))
    eg_end(m)
    # Word fits: no scope, wrong shape, excluded operands, every bound combination.
    print(eg_fits(bin(.plus, lit(1), lit(2))))
    m = eg_begin(pair(.and_, pair(.and_, bin(.ge, var(a), lit(1)), bin(.le, var(a), lit(5))), pair(.and_, bin(.ge, var(b), lit(BIG - 2)), bin(.le, var(c), lit(SMALL + 2)))), true)
    state()
    aux2 = bin(.plus, lit(1), lit(2)); nodes[aux2].aux = 1
    print("{eg_fits(fresh(.call))} {eg_fits(aux2)} {eg_fits(bin(.star, lit(1), lit(2)))}")
    big = lit(1); big_nodes[big] = true
    wide = lit(1); wide_nodes[wide] = true
    big2 = lit(1); big_nodes[big2] = true
    wide2 = lit(1); wide_nodes[wide2] = true
    print("{eg_fits(bin(.plus, big, lit(1)))} {eg_fits(bin(.plus, lit(1), big2))} {eg_fits(bin(.plus, wide, lit(1)))} {eg_fits(bin(.plus, lit(1), wide2))}")
    terms = [var(a), var(b), var(c), lit(1), lit(-1), lit(BIG), lit(SMALL)]
    loop op in [Tok.plus, Tok.minus]:
        loop x in terms:
            row = ""
            loop y in terms: row = "{row} {eg_fits(bin(op, x, y))}"
            print(row)
    # An empty interval (contradictory guards) never fits.
    e = eg_begin(pair(.and_, bin(.ge, var(c), lit(9)), bin(.le, var(c), lit(1))), true)
    bounds(var(c))
    print(eg_fits(bin(.plus, var(c), lit(1))))
    print(eg_fits(bin(.plus, lit(1), var(c))))
    eg_end(e)
    eg_end(m)
    state()
    print("guards ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_exact_guard_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/exact_guards.jo').read_text()
    state = state[state.index('struct ExactGuard'):]
    output = compare_narrow(compiler, tmp_path, release,
                            ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'refinement_types', 'exact_guard_ops'), DRIVER,
                            doubles={'services.jo': SERVICES, 'exact_guards.jo': state},
                            services=('ast', 'check', 'checked_eval', 'exact', 'expr', 'lower', 'types'))
    assert output.endswith(b'guards ok\n')
    for text in (b'deep 32', b'bound', b'stack [', b'cond '):
        assert text in output, text
