"""A small fact engine for selector leaf differentials: values are table rows, calls leave a log."""

FACT_SERVICES = r'''use 'source_types.dewy'
use 'node_store.dewy'
use 'checker_types.dewy'
use 'checker_state.dewy'
use 'checker_tokens.dewy'
use 'refinement_types.dewy'
const FACT_CAP = 256
const FACT_ELEMENT_VALUE = -17
const FACT_ELEMENT_COPY = -19
const T_INT = 2
const T_MATH_INT = 3
const T_U64 = 4
const T_MATH_LIKE = 5
const T_BOOL = 1
const T_ARRAY_OF_INT = 50
const T_ARRAY_OF_BOOL = 51
const T_RANGE = 52
const T_OTHER = 53
const T_FIXED = 54
struct FactProjection:
    base: int
    selector: int
    element: bool
    value: int
struct FactState:
    projections: FactProjection[]
nodes: Node[] = [Node()]
lists: i32[]
lib_dir = "/lib"
fact_terms: FactTerm[] = [FactTerm()]
fact_constructor_actuals: {int: int[]} = {}
known: {int: FactBound} = {}
inventories: {int: int[]} = {}
call_kinds: {int: int} = {}
needs_hold = true
log = (text: str): print(text)
kid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])
nkids = (n: int) -> int: int(nodes[n].nlist)
ntype = (n: int) -> int: int(nodes[n].type)
representation_type = (t: int) -> int: t
is_int = (t: int) -> bool: t == T_INT or t == T_MATH_INT or t == T_U64 or t == T_MATH_LIKE
telem = (t: int) -> int: if t == T_ARRAY_OF_BOOL: T_BOOL else: T_INT
tkind = (t: int) -> TK:
    if t == T_ARRAY_OF_INT or t == T_ARRAY_OF_BOOL: return .array
    if t == T_FIXED: return .fixed
    .int_
fixed_len = (t: int) -> int: 12
mk_array = (e: int) -> int: if e == T_BOOL: T_ARRAY_OF_BOOL else: T_ARRAY_OF_INT
is_dewy_range_type = (t: int, name: str) -> bool: t == T_RANGE and name == "IntRange"
wit_text = (e: int, depth: int = 0) -> str: if e % 2 == 0: "" else: "text{e}"
bc_int = (v: int, pos: int) -> int:
    nodes.push(Node(kind=.int_lit, pos=pos, ival=v))
    nodes.len() - 1
fact_new = (s: mut FactState, b: FactBound, term: FactTerm = FactTerm()) -> int:
    fact_terms.push(term)
    v = fact_terms.len() - 1
    known[v] = b
    log("new {v} {b.lo} {b.hi} {b.wide} {term.type} {term.origin}")
    v
constants: {int: int} = {}
fact_constant = (s: mut FactState, x: int, at: int = 0) -> int:
    if constants.has(x): return constants[x]
    v = fact_new(s, FactBound(x, x))
    constants[x] = v
    v
fact_fresh = (s: mut FactState, t: int) -> int: fact_new(s, FactBound(wide=true), FactTerm(type = t))
fact_bound = (s: FactState, v: int) -> FactBound: known.get(v) ?? FactBound(wide=true)
fact_length_max = () -> int: 1000000
fact_projection_find = (s: FactState, base: int, selector: int, element: bool) -> int:
    loop i in [0..s.projections.len()):
        p = s.projections[i]
        if p.base == base and p.selector == selector and p.element == element: return i
    -1
fact_add_projection = (s: mut FactState, p: FactProjection):
    log("projection {p.base} {p.selector} {p.element} {p.value}")
    s.projections.push(p)
fact_project = (s: mut FactState, base: int, selector: int, element: bool, t: int) -> int:
    found = fact_projection_find(s, base, selector, element)
    if found >= 0: return s.projections[found].value
    v = fact_fresh(s, t)
    fact_add_projection(s, FactProjection(base, selector, element, v))
    v
fact_compare = (s: FactState, op: Tok, a: int, b: int) -> int:
    x = fact_bound(s, a); y = fact_bound(s, b)
    if x.wide or y.wide or x.lo != x.hi or y.lo != y.hi: return 0
    if op == .lt: return if x.lo < y.lo: 1 else: -1
    if op == .le: return if x.lo <= y.lo: 1 else: -1
    if op == .gt: return if x.lo > y.lo: 1 else: -1
    if op == .ge: return if x.lo >= y.lo: 1 else: -1
    if x.lo == y.lo: 1 else: -1
fact_arithmetic = (s: mut FactState, n: int, op: Tok, a: int, b: int) -> int:
    x = fact_bound(s, a); y = fact_bound(s, b)
    log("arithmetic {int(op)} {a} {b} {nodes[n].type}")
    if x.wide or y.wide or x.lo != x.hi or y.lo != y.hi: return fact_fresh(s, T_INT)
    if op == .plus: return fact_constant(s, x.lo + y.lo)
    if op == .minus: return fact_constant(s, x.lo - y.lo)
    fact_constant(s, x.lo * y.lo)
fact_inventory = (s: FactState, v: int) -> int[]: inventories.get(v) ?? []
fact_host_endpoint = (s: FactState, v: int, upper: bool) -> bool: (v % 2 == 0) == upper
fact_nd_call = (n: int) -> int: call_kinds.get(n) ?? 0
fact_nd_need = (n: int, s: mut FactState, op: Tok, a: int, b: int, relation: str) -> bool:
    log("need {n} {int(op)} {a} {b} {relation}")
    needs_hold
fact_nd_store = (n: int, s: mut FactState, at: int, reason: FactReason): log("store {n} {at} {int(reason)}")
fact_nd_shape = (s: mut FactState, v: int) -> int: fact_project(s, v, -40, false, T_ARRAY_OF_INT)
fact_nd_dim = (s: mut FactState, v: int, t: int, axis: int) -> int: fact_project(s, v, -41 - axis, false, T_INT)
fact_nd_data_length = (s: mut FactState, v: int) -> int: fact_project(s, v, -42, false, T_INT)
fact_nd_valid = (s: mut FactState, v: int) -> int: fact_project(s, v, -43, false, T_INT)
fact_nd_make = (n: int, s: mut FactState, dims: int[], data: int = 0, result_type: int = 0) -> int:
    log("make {n} {dims} {data} {result_type}")
    fact_fresh(s, T_OTHER)
'''
