"""The call checker's queries (intrinsic_of, ctx_dependent) match frozen Jo and expr.jo's answers."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
intrinsic_names: int[] = [0, 3, 0, 1]
set_name = 2
query_input = CheckerCallQueryInput(&nodes, &lists, &files, &intrinsic_names, &set_name)
query_binding = checker_call_queries_bind(&query_input)
mk = (kind: NK, flags: int = 0, t: int = 0, children: int[] = []) -> int:
    n = node(kind, 0, 0, 0, children)
    nodes[n].flags = i32(flags); nodes[n].type = i32(t)
    n
ask = (label: str, n: int): print("{label}:{ctx_dependent(n)}")
main = ():
    prepare()
    loop name in [-1, 0, 1, 2, 3, 4, 99]: print("intrinsic:{name}:{intrinsic_of(name)}")
    # (oversized literals, negated or not)
    big = mk(.call); nodes[big].aux2 = -1
    ask("big", big)
    neg = mk(.unary); nodes[neg].op = 59; nodes[neg].a = i32(big)
    ask("neg", neg)
    negneg = mk(.unary); nodes[negneg].op = 59; nodes[negneg].a = i32(neg)
    ask("negneg", negneg)
    tilde = mk(.unary); nodes[tilde].op = 66; nodes[tilde].a = i32(big)
    ask("tilde", tilde)
    small = mk(.int_lit)
    neg_small = mk(.unary); nodes[neg_small].op = 59; nodes[neg_small].a = i32(small)
    ask("neg_small", neg_small)
    # (calls: a set literal, `.v(args)`, anything else; typed ones are settled)
    set_callee = mk(.ident); nodes[set_callee].name = i32(2)
    set_call = mk(.call, 0, 0, [small]); nodes[set_call].a = i32(set_callee)
    ask("set", set_call)
    set_two = mk(.call, 0, 0, [small, small]); nodes[set_two].a = i32(set_callee)
    ask("set_two", set_two)
    other_callee = mk(.ident); nodes[other_callee].name = i32(1)
    other_call = mk(.call, 0, 0, [small]); nodes[other_call].a = i32(other_callee)
    ask("other_call", other_call)
    dot_callee = mk(.dotname)
    dot_call = mk(.call); nodes[dot_call].a = i32(dot_callee)
    ask("dot_call", dot_call)
    typed_call = mk(.call, 0, T_INT, [small]); nodes[typed_call].a = i32(set_callee)
    ask("typed_call", typed_call)
    # (names as function values, `.v`, and the kinds that always wait)
    ask("ident", mk(.ident))
    ask("fnref_ident", mk(.ident, 4096))
    ask("fnref_field", mk(.field, 4096))
    ask("fnref_apply", mk(.typeapply, 4096))
    ask("dotname", mk(.dotname))
    ask("dotname_typed", mk(.dotname, 0, T_INT))
    ask("lambda", mk(.lambda))
    ask("none", mk(.none_lit))
    ask("hole", mk(.hole))
    ask("record", mk(.record_lit))
    ask("tuple", mk(.tuple))
    # (comprehensions until checked)
    ask("block", mk(.block))
    ask("comprehension", mk(.block, 67108864))
    ask("comprehension_checked", mk(.block, 67108864 + 128))
    # (Dewy conditionals and literals until checked; Jo ones are not)
    loop dewy in [false, true]:
        files[0].is_dewy = dewy
        ask("if:{dewy}", mk(.if_))
        ask("if_checked:{dewy}", mk(.if_, 128))
        ask("match:{dewy}", mk(.match_))
        ask("map_empty:{dewy}", mk(.map_lit))
        ask("map:{dewy}", mk(.map_lit, 0, 0, [small]))
        ask("map_typed:{dewy}", mk(.map_lit, 0, T_INT, [small]))
        ask("map_checked:{dewy}", mk(.map_lit, 128, 0, [small]))
        empty = mk(.array)
        ask("array_empty:{dewy}", empty)
        nodes[empty].b = 1
        ask("array_empty_typed:{dewy}", empty)
        ask("array:{dewy}", mk(.array, 0, 0, [small, small]))
        ask("array_checked:{dewy}", mk(.array, 128, 0, [small, small]))
        ask("array_lambda:{dewy}", mk(.array, 128, 0, [small, mk(.lambda)]))
        nested = mk(.array, 128, 0, [small, mk(.array, 128, 0, [small, neg])])
        ask("array_nested:{dewy}", nested)
        ask("array_typed:{dewy}", mk(.array, 0, T_INT, [small, small]))
    print("ok")
'''

# expr.jo's answers before the move, for the cases above.
EXPECTED = '''intrinsic:-1:-1
intrinsic:0:-1
intrinsic:1:2
intrinsic:2:-1
intrinsic:3:0
intrinsic:4:-1
intrinsic:99:-1
big:true
neg:true
negneg:true
tilde:false
neg_small:false
set:true
set_two:false
other_call:false
dot_call:true
typed_call:false
ident:false
fnref_ident:true
fnref_field:true
fnref_apply:true
dotname:true
dotname_typed:false
lambda:true
none:true
hole:true
record:true
tuple:false
block:false
comprehension:true
comprehension_checked:false
if:false:false
if_checked:false:false
match:false:false
map_empty:false:true
map:false:false
map_typed:false:false
map_checked:false:false
array_empty:false:true
array_empty_typed:false:false
array:false:false
array_checked:false:false
array_lambda:false:true
array_nested:false:true
array_typed:false:false
if:true:true
if_checked:true:false
match:true:true
map_empty:true:true
map:true:true
map_typed:true:false
map_checked:true:false
array_empty:true:true
array_empty_typed:true:false
array:true:true
array_checked:true:false
array_lambda:true:true
array_nested:true:true
array_typed:true:false
ok
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_queries_twins(compiler, tmp_path, release):  # noqa: F811
    out = compare(compiler, tmp_path, release, DRIVER, extra_stems=('checker_call_queries',))
    assert out.decode() == EXPECTED
