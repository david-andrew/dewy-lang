"""Inferred text and integer domains: writes, captures, matches, conversions and members match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
const NF_CHECKED = 1
const NF_U64 = 2
const LF_CAPTURE = 1
const LF_VALUECAP = 2
const FK_NORMAL = 0
const T_STR = 1
const T_NEVER = 2
const T_MATH_INT = 3
const T_INT = 4
struct Watch:
    text_domains: int
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
syms: Sym[] = [Sym()]
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[] = [FnCtx(inst=2, loop_depth=1), FnCtx(inst=3, loop_depth=9000)]
cx = -1
statement_watch = Watch(0)
last_checked = 0
scope: {int: int} = {}
narrowed: {int: int} = {}
aliases: {int: int} = {}
str_sets: str[][] = [[], ["n1", "n2"], ["n1"]]
names: {str: int} = {}
name_texts: str[] = [""]
allowed_known = true
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
nkids = (n: int) -> int: int(nodes[n].nlist)
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
alias_global = (l: int) -> int: aliases.get(l) ?? -1
narrowed_var = (l: int) -> int: narrowed.get(l) ?? 0
cur_mod = () -> int: 8
new_inst = (kind: int, m: int, base: str) -> int:
    fns.push(FnInst(kind=i32(kind), mod=i32(m), sym=base))
    fns.len() - 1
lookup = (name: int) -> int: scope.get(name) ?? 0
check_expr = (n: int, e: int) -> int:
    print("check_expr {n} {e}")
    last_checked = n
    int(nodes[n].type)
ntype = (n: int) -> int: int(nodes[n].type)
bc_block = (items: int[], pos: int) -> int:
    n = mk(.block, pos)
    set_list(n, items)
    n
int_intervals = (t: int) -> (bool, int[]):
    print("int_intervals {t}")
    (allowed_known, [0, 10])
representation_type = (t: int) -> int: t
str_set_const = (set: int, i: int, pos: int) -> int:
    # (making a node can move the arena under a caller's chosen destination)
    loop nodes.len() % 4096 != 0: nodes.push(Node())
    nodes.push(Node())
    n = mk(.str_lit, pos)
    nodes[n].sval = i32(set * 100)
    n
str_set_text = (set: int) -> str: "set{set}"
mk_array = (t: int) -> int: t + 50
mk_fn = (params: int[], ret: int, mutmask: int, labels: int = 0, defaults: int = 0, pack: bool = false) -> int:
    print("mk_fn {params} {ret} {mutmask}")
    ret + 60
intern = (s: str) -> int:
    if let id = names.get(s): return id
    name_texts.push(s)
    names[s] = name_texts.len() - 1
    names[s]
name_of = (n: int) -> str: name_texts[n]
fatal = (pos: int, msg: str):
    print("fatal {pos}: {msg}")
    exit(3)
'''

DRIVER = r'''
use 'string_domains.jo'
text_lit = (s: str) -> int:
    n = mk(.str_lit, 5)
    nodes[n].sval = i32(intern(s))
    n
int_lit = (v: int) -> int:
    n = mk(.int_lit, 5)
    nodes[n].ival = v
    n
other = () -> int: mk(.call, 6)
choose = (a: int, b: int) -> int:
    n = mk(.if_, 5)
    nodes[n].b = i32(a); nodes[n].c = i32(b)
    n
local_ident = (l: int) -> int:
    n = mk(.ident, 7)
    nodes[n].aux = 1; nodes[n].sym = i32(l)
    n
local_of = (flags: int, outer: int) -> int:
    locals.push(Local(flags=i32(flags), outer=i32(outer)))
    locals.len() - 1
domains = () -> str:
    keys = string_domains.keys(); keys.sort()
    s = ""
    loop k in keys: s = "{s} {k}:{string_domains[k]}"
    "{s} watch={statement_watch.text_domains}"
ints = (): print(int_log)
arm_of = (texts: str[]) -> int:
    ps: int[]
    loop t in texts:
        p = mk(.plit, 5)
        nodes[p].a = i32(text_lit(t))
        ps.push(p)
    other_p = mk(.pwild, 5)
    non_text = mk(.plit, 5)
    nodes[non_text].a = i32(int_lit(1))
    ps.push(other_p); ps.push(non_text)
    a = mk(.arm, 5)
    set_list(a, ps)
    a
match_on = (binding_node: int, arms: int[], pos: int) -> int:
    m = mk(.match_, pos)
    nodes[m].a = i32(binding_node)
    set_list(m, arms)
    m
everything = ():
    loop texts in ["n1", "n2", "n3"]: intern(texts)
    # Declarations: a literal, an aux literal, a conditional, an opaque value, none.
    string_domain_declare(1, text_lit("n1"))
    raw = text_lit("n2"); nodes[raw].aux = 1
    string_domain_declare(2, raw)
    string_domain_declare(3, choose(text_lit("n1"), text_lit("n2")))
    string_domain_declare(4, other())
    string_domain_declare(5, 0)
    print(domains())
    # Which binding a name is.
    plain = local_of(0, 0)
    captured = local_of(1, plain)
    value_cap = local_of(3, plain)
    narrowed_l = local_of(0, 0)
    narrowed[narrowed_l] = captured
    aliased = local_of(0, 0)
    aliases[aliased] = 44
    print("{string_domain_binding(mk(.call, 1))} {string_domain_binding(local_ident(plain))} {string_domain_binding(local_ident(captured))} {string_domain_binding(local_ident(value_cap))} {string_domain_binding(local_ident(narrowed_l))} {string_domain_binding(local_ident(aliased))}")
    g = mk(.ident, 1); nodes[g].aux = 2; nodes[g].sym = 9
    fn_name = mk(.ident, 1); nodes[fn_name].aux = 3
    print("{string_domain_binding(g)} {string_domain_binding(fn_name)}")
    # Writes: to no domain, an open one, a literal, an opaque value that opens it.
    string_domains = {}
    string_domains[plain] = [intern("n1")]
    string_domain_write(local_ident(value_cap), text_lit("n3"))
    print(domains())
    string_domain_write(local_ident(plain), text_lit("n2"))
    print(domains())
    string_domain_write(local_ident(plain), text_lit("n2"))
    print(domains())
    string_domain_write(local_ident(plain), other())
    print(domains())
    string_domain_write(local_ident(plain), text_lit("n3"))
    print(domains())
    string_domains[plain] = [intern("n1")]
    # Captures, values, matches.
    inner = local_of(0, 0)
    root_cap = local_of(1, plain)
    string_domain_capture(inner, root_cap)
    print("{domains()} {string_domain_captures.len()} {string_domain_values(inner)} {string_domain_values(plain)}")
    print(string_domain_match(match_on(local_ident(value_cap), [], 1)))
    print(string_domain_match(match_on(local_ident(plain), [arm_of(["n1"])], 2)))
    string_domains_finish()
    string_domain_matches = []
    # Conversions.
    print(string_domain_conversion(local_ident(value_cap), 1))
    print(string_domain_conversion(local_ident(plain), 1))
    print(string_domain_conversion(local_ident(plain), 2))
    print(string_domain_conversions)
    # Sequences: refusals and a literal array, then materialized in text order.
    sym_of = (name: int, kind: SK) -> int:
        syms.push(Sym(kind=kind))
        scope[name] = syms.len() - 1
        syms.len() - 1
    print(sym_of(70, .local))
    sym_of(71, .global)
    sym_of(72, .fns)
    call_with = (arg: int) -> int:
        c = mk(.call, 15)
        set_list(c, [arg])
        c
    name_node = (name: int, l: int) -> int:
        n = mk(.ident, 16)
        nodes[n].name = i32(name); nodes[n].aux = 1; nodes[n].sym = i32(l)
        n
    print(string_domain_members(mk(.call, 15)))
    print(string_domain_members(call_with(mk(.int_lit, 15))))
    print(string_domain_members(call_with(name_node(73, plain))))
    print(string_domain_members(call_with(name_node(72, plain))))
    string_domains[plain] = [intern("n2"), intern("n1"), intern("n2")]
    seq = call_with(name_node(70, plain))
    print(string_domain_members(seq))
    print("{nodes[seq].kind == .call} {nodes[seq].pos} {nodes[seq].sym} {nodes[seq].type} {nodes[seq].flags} {fns.len()}")
    made = fns[int(nodes[seq].sym)]
    print("{made.sym} {made.mod} {made.ret} {made.fntype} {made.state} {made.noinline} {nkids(int(made.body))}")
    stops = mk(.call, 17)
    string_domains[value_cap] = [intern("n1")]
    string_domain_conversions = [(18, plain, 1), (19, plain, 1), (20, value_cap, 2)]
    string_domain_conversion_stops[1] = stops
    string_domain_conversion_stops[2] = stops + 100
    loop nodes.len() < stops + 101: nodes.push(Node())
    string_domains_materialize()
    print("{nodes[stops].kind == .str_lit} {nodes[stops].sval} {made.state} {fns[int(nodes[seq].sym)].state}")
    arr = int(nodes[kid(int(made.body), 0)].a)
    loop item in kids(arr): print("{name_of(int(nodes[item].sval))} {nodes[item].type} {nodes[item].flags}")
    # Integers: a site, declarations and writes, each log record.
    print(int_site())
    cx = 0
    print(int_site())
    cx = 1
    print(int_site())
    int_domain_declare(1, int_lit(5))
    int_domain_declare(-3, int_lit(6))
    neg = mk(.int_lit, 5); nodes[neg].ival = -1; nodes[neg].flags = i32(NF_U64)
    int_domain_declare(2, neg)
    int_domain_declare(3, choose(int_lit(1), int_lit(2)))
    int_domain_declare(4, other())
    ints()
    int_log = []
    i1 = local_of(0, 0)
    int_domain_write(local_ident(i1), int_lit(4), 0)
    int_domain_write(local_ident(i1), other(), 0)
    int_domain_write(local_ident(i1), int_lit(2), int(Tok.pluseq))
    int_domain_write(local_ident(i1), int_lit(2), int(Tok.minuseq))
    int_domain_write(local_ident(i1), choose(int_lit(1), int_lit(2)), int(Tok.pluseq))
    int_domain_write(local_ident(i1), int_lit(2), int(Tok.stareq))
    int_domain_write(g, int_lit(2), int(Tok.pluseq))
    int_domain_write(mk(.call, 1), int_lit(2), 0)
    ints()
    int_domain_capture(i1 + 1, root_cap)
    ints()
    int_log = []
    print("{int_domain_match(match_on(mk(.call, 1), [], 1), [1])} {int_domain_match(match_on(local_ident(i1), [], 1), [1])}")
    # A conversion through its coercions, and what isn't one.
    typed = local_ident(i1); nodes[typed].type = i32(T_MATH_INT)
    wrapped = mk(.conv, 1); nodes[wrapped].a = i32(typed)
    int_domain_conversion(wrapped, 1)
    other_type = local_ident(i1); nodes[other_type].type = i32(T_INT)
    int_domain_conversion(other_type, 1)
    int_domain_conversion(mk(.call, 1), 1)
    no_binding = mk(.ident, 1); nodes[no_binding].aux = 3; nodes[no_binding].type = i32(T_MATH_INT)
    int_domain_conversion(no_binding, 1)
    print(int_domain_conversions)
    int_domain_matches = []
    int_domain_conversions = []
    # Settling: nothing demanded; matches covered; conversions proved or not.
    int_domains_finish()
    a1 = local_of(0, 0); a2 = local_of(0, 0); a3 = local_of(0, 0)
    int_domain_declare(a1, int_lit(1)); int_domain_write(local_ident(a1), int_lit(2), 0)
    int_domain_declare(a2, int_lit(5)); int_domain_write(local_ident(a2), int_lit(50), 0)
    int_domain_declare(a3, other())
    int_domain_declare(a3, int_lit(1)); int_domain_write(local_ident(a3), other(), 0)
    print(int_domain_match(match_on(local_ident(a1), [], 21), [1, 2]))
    typed_a = (l: int) -> int:
        n = local_ident(l)
        nodes[n].type = i32(T_MATH_INT)
        n
    c1 = typed_a(a1); c2 = typed_a(a2); c3 = typed_a(a3)
    int_domain_conversion(c1, 1); int_domain_conversion(c2, 1); int_domain_conversion(c3, 1)
    int_domains_finish()
    print("{int_domain_proven.has(c1)} {int_domain_proven.has(c2)} {int_domain_proven.has(c3)} {int_log.len()} {int_domain_states.len()}")
    allowed_known = false
    int_domain_declare(a1, int_lit(1))
    c4 = typed_a(a1)
    int_domain_conversion(c4, 1)
    int_domains_finish()
    print(int_domain_proven.has(c4))
    allowed_known = true
main = ():
    case = if args().len() > 1: args()[1] else: "all"
    if case == "all": everything()
    else: failing(case)
    print("{case} ok")
failing = (case: str):
    loop texts in ["n1", "n2", "n3"]: intern(texts)
    plain = local_of(0, 0)
    if case == "open match":
        string_domains[plain] = []
        string_domain_match(match_on(local_ident(plain), [], 31))
        string_domains_finish()
    if case == "missing arm":
        string_domains[plain] = [intern("n1"), intern("n2"), intern("n3"), intern("n2")]
        string_domain_match(match_on(local_ident(plain), [arm_of(["n1"])], 32))
        string_domains_finish()
    if case == "not a member":
        string_domains[plain] = [intern("n3")]
        string_domain_conversion(local_ident(plain), 1)
        string_domains_materialize()
    if case == "members open":
        syms.push(Sym(kind=.local))
        scope[70] = syms.len() - 1
        n = mk(.ident, 16)
        nodes[n].name = 70; nodes[n].aux = 1; nodes[n].sym = i32(plain)
        c = mk(.call, 15)
        set_list(c, [n])
        string_domain_members(c)
    if case == "members later open":
        string_domain_sequences = [(mk(.array, 33), plain)]
        string_domains[plain] = []
        string_domains_materialize()
    if case == "int unbounded":
        int_domain_match(match_on(local_ident(plain), [], 34), [1])
        int_domains_finish()
    if case == "int open":
        int_domain_declare(plain, int_lit(1))
        int_domain_write(local_ident(plain), mk(.call, 1), 0)
        int_domain_match(match_on(local_ident(plain), [], 35), [1])
        int_domains_finish()
    if case == "int missing":
        int_domain_declare(plain, int_lit(1))
        int_domain_write(local_ident(plain), int_lit(3), 0)
        int_domain_match(match_on(local_ident(plain), [], 36), [1])
        int_domains_finish()
'''

FAILS = (('open match', b'domain is open'), ('missing arm', b"no arm for 'n2', 'n3'"), ('not a member', b'is not one of set1'),
         ('members open', b'needs an inferred finite'), ('members later open', b'a nonliteral write leaves it open'),
         ('int unbounded', b'add a `_ => ...`'), ('int open', b'not a bounded set'), ('int missing', b'no arm for'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_string_domain_twins(compiler, tmp_path, release):  # noqa: F811
    state = (ROOT / 'compiler/string_domains.jo').read_text()
    state = state[state.index('string_set_obligations: {int'):]
    outputs = compare_narrow(compiler, tmp_path, release,
                             ('checker_tokens', 'node_store', 'checker_types', 'checker_state', 'literal_domains', 'int_domains', 'intervals', 'text_domains', 'string_domain_ops'), DRIVER,
                             doubles={'services.jo': SERVICES, 'string_domains.jo': "use 'services.jo'\nuse 'node_store.dewy'\nuse 'checker_tokens.dewy'\nuse 'literal_domains.dewy'\nuse 'int_domains.dewy'\n" + state},
                             invocations=(((), 0), *(((case,), 3) for case, _ in FAILS)),
                             services=('ast', 'check', 'checker_expr', 'expr', 'facts', 'lex', 'refine', 'types', 'util'))
    assert outputs[0].endswith(b'all ok\n')
    for output, (_, text) in zip(outputs[1:], FAILS):
        assert text in output, (text, output)
