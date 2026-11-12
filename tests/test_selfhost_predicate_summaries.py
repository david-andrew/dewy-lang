"""Closed Boolean summaries: what is accepted, its budget and instantiation match frozen Jo."""
import re

import pytest

from tests.selfhost_fact_double import FACT_SERVICES
from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

STEMS = ('source_types', 'node_store', 'checker_types', 'checker_state', 'checker_tokens', 'refinement_types', 'predicate_summaries')
SERVICES = ('facts', 'expr', 'lex', 'util', 'ast', 'check', 'types', 'ownership', 'refine', 'checked_eval', 'facts_forgets')
STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/predicate_facts.jo').read_text())

EXTRA = r'''
const NF_U64 = 8
const NF_EXPLICIT_INTEGER = 16
const NF_RECORD = 32
const FK_INIT = 4
const LF_MUTPARAM = 64
enum CV: none_, int_, float_
enum IN: none_, len, push
ownership_fact_cleanup = false
pending_drop = 0
drop_queries = 0
fact_drop_pending = (f: int) -> bool:
    drop_queries += 1
    f == pending_drop
fns: FnInst[] = [FnInst()]
locals: Local[] = [Local()]
fact_type = (t: int) -> int: t
fact_scalar = (t: int) -> bool: t != T_OTHER
fact_comparison = (op: Tok) -> bool: op == .lt or op == .eq or op == .le
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
ref_encoded = (x: int, t: int) -> int: x * 2 + t
cx_token = (value: int) -> Tok: value as Tok
fact_domain = (t: int, reason: FactReason = .missing, at: int = 0) -> FactBound: FactBound(wide=true)
'''

DRIVER = r'''
use 'predicate_facts.jo'
s = FactState()
n_ = (k: NK, a: int = 0, b: int = 0, t: int = T_INT) -> int:
    nodes.push(Node(kind=k, a=i32(a), b=i32(b), type=i32(t)))
    nodes.len() - 1
list = (k: NK, items: int[], t: int = T_INT) -> int:
    n = n_(k, 0, 0, t)
    node_set_list(mut nodes, mut lists, n, items)
    n
p = (l: int, t: int = T_INT) -> int:
    n = n_(.ident, 0, 0, t)
    nodes[n].aux = i32(int(SK.local)); nodes[n].sym = i32(l)
    n
lit = (v: int, t: int = T_INT) -> int:
    n = n_(.int_lit, 0, 0, t); nodes[n].ival = v; n
conv = (a: int, t: int = T_INT, how: int = 1) -> int:
    n = n_(.conv, a, 0, t); nodes[n].aux = i32(how); n
binary = (op: Tok, a: int, b: int) -> int:
    n = n_(.binary, a, b, T_BOOL); nodes[n].op = i32(int(op)); n
length = (a: int) -> int:
    n = list(.intrinsic, [a]); nodes[n].aux = i32(int(IN.len)); n
show_all = ():
    loop i in [0..fact_predicate_nodes.len()):
        t = fact_predicate_nodes[i]
        print("{i}: {int(t.op)} {t.parameter} {t.literal} {t.a} {t.b} {t.length} {t.element}")
summary = (what: str, body: int, nparams: int = 2, flags: int = 0):
    params: int[]
    loop i in [0..nparams):
        locals.push(Local(flags=i32(if i == 1: flags else: 0)))
        params.push(locals.len() - 1)
    fns.push(FnInst(body=i32(body), params=params, state=2))
    print("== {what}: {fact_predicate_summary(fns.len() - 1)}")
    show_all()
main = ():
    base = locals.len()
    a = base; b = base + 1
    next = () -> int: locals.len()
    # A parameter at each call's own locals: bodies are built with the next two local numbers.
    summary("parameter", p(next()))
    summary("other local", p(1))
    summary("empty", 0)
    summary("not_found", n_(.call))
    summary("literal", lit(7))
    summary("bool", n_(.bool_lit, 0, 0, T_BOOL))
    summary("u64 literal", lit(7, T_U64))
    flagged = lit(7); nodes[flagged].flags = i32(NF_U64)
    summary("flagged literal", flagged)
    summary("return", n_(.return_, lit(1)))
    summary("statement", n_(.exprstmt, lit(1)))
    summary("not", n_(.not_, p(next())))
    summary("not none", n_(.not_, n_(.call)))
    summary("and", n_(.and_, p(next()), lit(1)))
    summary("or", n_(.or_, lit(1), p(next() + 1)))
    summary("or none", n_(.or_, lit(1), n_(.call)))
    summary("less", binary(.lt, p(next()), lit(3)))
    summary("plus", binary(.plus, p(next()), lit(3)))
    summary("binary u64", binary(.lt, p(next(), T_U64), lit(3)))
    summary("binary u64 right", binary(.lt, p(next()), lit(3, T_U64)))
    summary("binary float", binary(.lt, p(next(), T_OTHER), lit(3)))
    aux = binary(.lt, p(next()), lit(3)); nodes[aux].aux = 1
    summary("binary aux", aux)
    summary("length", length(p(next(), T_ARRAY_OF_INT)))
    summary("length other", length(p(next(), T_OTHER)))
    summary("length none", length(n_(.call, 0, 0, T_ARRAY_OF_INT)))
    summary("element", n_(.index, p(next(), T_ARRAY_OF_INT), p(next() + 1)))
    summary("fixed element", n_(.index, p(next(), T_FIXED), lit(1)))
    summary("bool element", n_(.index, p(next(), T_ARRAY_OF_INT), lit(1), T_BOOL))
    summary("u64 element", n_(.index, p(next(), T_ARRAY_OF_INT), lit(1), T_U64))
    summary("struct element", n_(.index, p(next(), T_ARRAY_OF_INT), lit(1), T_OTHER))
    summary("not an array", n_(.index, p(next(), T_OTHER), lit(1)))
    summary("no index", n_(.index, p(next(), T_ARRAY_OF_INT)))
    summary("element no base", n_(.index, n_(.call, 0, 0, T_ARRAY_OF_INT), lit(1)))
    summary("element no index", n_(.index, p(next(), T_ARRAY_OF_INT), n_(.call)))
    # Index and widening conversions.
    peeled = conv(p(next(), T_MATH_INT))
    summary("index conv", n_(.index, p(next(), T_ARRAY_OF_INT), peeled))
    explicit = conv(p(next(), T_MATH_INT)); nodes[explicit].flags = i32(NF_EXPLICIT_INTEGER)
    summary("explicit index", n_(.index, p(next(), T_ARRAY_OF_INT), explicit))
    summary("widen", conv(p(next(), T_MATH_LIKE)))
    summary("widen u64", conv(p(next(), T_U64)))
    summary("widen math", conv(p(next(), T_MATH_INT)))
    summary("into math", conv(p(next()), T_MATH_INT))
    summary("math into math", conv(p(next(), T_MATH_INT), T_MATH_INT))
    summary("widen other", conv(p(next()), T_OTHER))
    summary("float conv", conv(p(next()), T_INT, 2))
    summary("widen float", conv(p(next(), T_OTHER)))
    # Value-parameter bindings lead a block.
    bind = (l: int) -> int:
        d = n_(.vardecl, 0, p(next() + 1))
        nodes[d].aux2 = 1; nodes[d].sym = i32(l)
        d
    summary("block empty", list(.block, []))
    summary("block", list(.block, [bind(90), p(90)]))
    summary("block unbound", list(.block, [bind(90), p(91)]))
    plain = bind(90); nodes[plain].aux2 = 0
    summary("not a binding", list(.block, [plain, p(90)]))
    with_list = bind(90); nodes[with_list].nlist = 1
    summary("bound list", list(.block, [with_list, p(90)]))
    other_source = n_(.vardecl, 0, lit(1)); nodes[other_source].aux2 = 1
    summary("bound literal", list(.block, [other_source, lit(1)]))
    no_source = n_(.vardecl); nodes[no_source].aux2 = 1
    summary("bound nothing", list(.block, [no_source, lit(1)]))
    outside = bind(90); nodes[nodes[outside].b].sym = 1
    summary("bound outside", list(.block, [outside, lit(1)]))
    # The budget: 32 nodes, then nothing; a failed summary leaves no nodes behind.
    deep = lit(1)
    loop i in [0..30): deep = n_(.not_, deep)
    summary("31 nodes", deep)
    deep = n_(.not_, n_(.not_, deep))
    before = fact_predicate_nodes.len()
    summary("33 nodes", deep)
    assert(fact_predicate_nodes.len() == before, "a failed summary is dropped")
    many: int[]
    loop i in [0..33): many.push(bind(90))
    many.push(p(90))
    summary("too many bindings", list(.block, many))
    # What keeps a function from having one, and the memo.
    summary("mutable parameter", p(next()), 2, LF_MUTPARAM)
    fns.push(FnInst(body=i32(lit(1)), state=1)); print(fact_predicate_summary(fns.len() - 1))
    fns.push(FnInst(state=2)); print(fact_predicate_summary(fns.len() - 1))
    capturing = FnInst(body=i32(lit(1)), state=2); capturing.caps = [Capture()]
    fns.push(capturing); print(fact_predicate_summary(fns.len() - 1))
    fns.push(FnInst(body=i32(lit(1)), state=2, kind=FK_INIT)); print(fact_predicate_summary(fns.len() - 1))
    fns.push(FnInst(body=i32(lit(1)), state=2)); f = fns.len() - 1
    first = fact_predicate_summary(f)
    fns[f].state = 1
    print(fact_predicate_summary(f) == first)
    ownership_fact_cleanup = true
    assert(fact_predicate_summary(f) == first)
    summary("unrelated hook", binary(.lt, p(next()), lit(3)))
    assert(drop_queries == 1)
    pending_drop = fns.len()
    before = fact_predicate_nodes.len()
    summary("pending cleanup", binary(.lt, p(next()), lit(3)))
    assert(fact_predicate_nodes.len() == before)
    assert(drop_queries == 2)
    summary("unsupported with hook", n_(.call))
    assert(drop_queries == 2)
    ownership_fact_cleanup = false
    # Instantiation.
    apply = (body: int, values: int[]):
        locals.push(Local()); locals.push(Local())
        fns.push(FnInst(body=i32(body), params=[locals.len() - 2, locals.len() - 1], state=2))
        print(fact_predicate_apply(fact_predicate_summary(fns.len() - 1), values, s))
    va = fact_constant(s, 5); vb = fact_constant(s, 6)
    apply(p(locals.len()), [va, vb])
    apply(p(locals.len() + 1), [va])
    apply(lit(9), [va])
    apply(n_(.not_, p(locals.len())), [va, vb])
    apply(n_(.not_, p(locals.len() + 1)), [va])
    apply(length(p(locals.len(), T_ARRAY_OF_INT)), [va, vb])
    apply(n_(.index, p(locals.len(), T_ARRAY_OF_INT), p(locals.len() + 1)), [va, vb])
    apply(n_(.index, p(locals.len(), T_ARRAY_OF_INT), p(locals.len() + 1)), [va])
    apply(binary(.lt, p(locals.len()), p(locals.len() + 1)), [va, vb])
    print("predicates ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_predicate_summaries_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release, STEMS, DRIVER,
                            doubles={'services.jo': FACT_SERVICES + EXTRA, 'predicate_facts.jo': "use 'checker_tokens.dewy'\n" + STATE}, services=SERVICES)
    assert output.endswith(b'predicates ok\n')
