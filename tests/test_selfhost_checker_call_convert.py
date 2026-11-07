"""Argument conversion and deferred branch scoring match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.test_selfhost_checker_call_resolve import DRIVER as RESOLVER, DOUBLES as RESOLVE_DOUBLES, JO as RESOLVE_JO

DOUBLES = {name: dict(pair) for name, pair in RESOLVE_DOUBLES.items()}
DOUBLES['checker_expr']['dewy'] += 'from p"services.jo" import cv_lookup\nlookup=(n:int64):>int64=>cv_lookup(n)\n'
DOUBLES['checker_expr']['jo'] += 'lookup = (n: int) -> int: cv_lookup(n)\n'
JO = dict(RESOLVE_JO)
# This differential exercises the real conversion leaf; resolver/cost tests use
# its module double. Remove that double and the old service stand-in here.
JO.pop('checker_call_convert.dewy', None)
JO.pop('checker_call_convert.jo', None)
start = JO['expr.jo'].index('call_conversion_double = ')
end = JO['expr.jo'].index('call_mutable_double = ', start)
JO['expr.jo'] = JO['expr.jo'][:start] + JO['expr.jo'][end:]
JO['expr.jo'] += r'''
branch_numeric = (a: int, hidden: int[]) -> bool: true
is_fn_type = (t: int) -> bool: tkind(t) == .fn_
bundled_bigint_type = (t: int) -> bool: false
word_rational_source = (a: int, t: int) -> bool: false
decimal_literal_tree = (a: int) -> bool: nodes[a].kind == .float_lit
oversized_literal = (a: int) -> bool: nodes[a].aux2 == 101
dewy_set_literal = (a: int) -> bool: false
is_dewy_set_type = (t: int) -> bool: false
variant_enum = (t: int, name: int) -> int: t
find_variant = (s: int, name: int) -> int: name - 1
array_has_spread = (a: int) -> bool: false
literal_union_member = (n: int, expected: int) -> int: 0
lambda_member = (n: int, expected: int) -> int: expected
function_member = (expected: int, count: int = -1) -> int: 0
fixed_literal_ok = (a: int, t: int) -> bool: nkids(a) == int(types[t].bits)
is_map_type = (t: int) -> bool: tkind(t) == .struct_ and types[t].bits == 91
dewy_positional_fits = (a: int, t: int) -> bool: true
dewy_record_target = (t: int) -> int: 0
dewy_record_spread_entries = (n: int, expected: int, ss: mut int[], capture: bool) -> int[]: kids(n)
charlike = (a: int) -> bool: nodes[a].aux2 == 102
union_target = (a: int, from: int, t: int) -> int: 0
call_string_cost = (a: int, p: int, sp: int, bs: mut int[]) -> int: 2
call_refined_literal_cost = (a: int, p: int) -> int: 0
lit_fits = (a: int, t: int) -> bool: nodes[a].ival >= -128 and nodes[a].ival <= 127
dewy_bigint_literal_target = (a: int, t: int) -> bool: false
fn_value_adapts = (a: int, from: int, t: int) -> bool: true
is_nd = (t: int) -> bool: false
nd_elem = (t: int) -> int: T_INT
'''
JO['ast.jo'] += r'''
const NF_GENERIC = 8192
const NF_SPREAD = 16384
const NF_U64 = 512
const NF_COMPREHENSION = 32768
kids = (a: int) -> int[]: decl_children.get(a) ?? []
clone = (a: int) -> int: n = nodes.len(); nodes.push(nodes[a]); n
'''
JO['types.jo'] += r'''
use 'type_constructors.dewy'
structs: StructInfo[]
fields: Field[]
T_INT = 0
T_MATH_INT = 0
T_U64 = 0
T_FLOAT = 0
is_int = (t: int) -> bool: tkind(t) == .int_
is_float = (t: int) -> bool: tkind(t) == .float_
is_union = (t: int) -> bool: tkind(t) == .enum_ and types[t].bits == 92
struct_targ = (s: int, i: int) -> int: T_INT
mk_array = (t: int) -> int: int(tb_mk_array(t))
'''
JO['check.jo'] += r'''
syms: Sym[] = [Sym()]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
binding_leaves = (xs: int[]) -> int[]: xs
check_struct_fields = (s: int): events.push("fields:{s}")
resolve_type = (n: int) -> int:
    if convert_error: print("signature-error"); exit(33)
    T_INT
subst = (p: int, bs: int[]) -> int: p
'''
JO['services.jo'] += 'cv_lookup = (name: int) -> int: name\n'
JO['units.jo'] += 'quantity_constant_fits = (a: int, t: int) -> bool: true\nquantity_int_promotes = (a: int, t: int) -> bool: false\ntime_constant_duration = (n: int, a: int, t: int) -> bool: false\n'
JO['effects.jo'] += "use 'ast.jo'\neffects_active = false\neffect_infer_callable = (a: int, t: int) -> int:\n    cv_effect_snapshot = nodes\n    loop i in [0..256): nodes.push(Node())\n    T_FLOAT\n"
JO['refine.jo'] += 'str_sets: str[][] = [[]]\n'
JO['effects.jo'] = JO['effects.jo'].replace('callable_contract = (t: int) -> int: 0',
    'callable_contract = (t: int) -> int: if t == cv_contract: 1 else: 0')
JO['poly_closure.jo'] += 'poly_matches = (a: int, b: int) -> bool: true\n'
JO['sibling_types.jo'] = 'sibling_array_source = (a: int, from: int, elem: int) -> bool: true\n'

JO['partition.jo'] = 'partition_active = false\npartition_slice = (a: int) -> bool: true\n'
JO['expr.jo'] += r'''
call_argument_error = (kind: int, a: int, pt: int): print("argument-error:{kind}"); exit(34)
written_at = (a: int) -> bool: nodes[a].aux2 == 103
check_place = (a: int, mutating: bool): events.push("place:{a}:{mutating}")
coerce = (a: int, pt: int) -> int: events.push("coerce:{a}:{pt}"); nodes[a].type = i32(pt); pt
path_narrows = 0
path_rooted = (a: int) -> bool: true
path_key = (a: int) -> str: "path"
path_forget = (key: str): events.push("forget:{key}")
'''
JO['refine.jo'] += r'''refine_arg_target = 0
ref_mutable_authority = (a: int): events.push("authority:{a}")
ref_nd_receivers: {int: bool} = {}
ref_self_direct_place = (a: int) -> bool: false
refine_storage = (a: int, t: int) -> int: t
ref_storage_contract = (t: int) -> bool: false
is_total_dict = (t: int) -> bool: false
'''
JO['types.jo'] += 'unify = (a: int, b: int) -> bool: a == b\n'

JO['services.jo'] = JO['services.jo'].replace(
    'nodes[a].kind == .lambda or nodes[a].kind == .hole',
    'nodes[a].kind == .lambda or nodes[a].kind == .hole or nodes[a].kind == .array or nodes[a].kind == .if_ or nodes[a].kind == .none_lit or nodes[a].kind == .dotname'
)

DRIVER = RESOLVER
for declaration in ('structs: StructInfo[]', 'fields: Field[]', 'T_INT = 0', 'T_MATH_INT = 0', 'T_U64 = 0', 'T_FLOAT = 0'):
    DRIVER = DRIVER.replace(declaration + '\n', '')
# The resolver driver defines unused helpers referencing resolve_fn_call. Its
# module is represented explicitly so lazy checking never pulls the compiler in.
JO['checker_call_resolve.jo'] = 'resolve_fn_call = (n: int, name: int, ds: int[], xs: int[], expected: int, closure: int = 0, ufcs: bool = false) -> int: 0\n'
JO['checker_call_resolve.dewy'] = 'resolve_fn_call=(n:int64 name:int64 ds:array<int64> xs:array<int64> expected:int64 closure:int64=0 ufcs:bool=false):>int64=>0\n'
DRIVER = "use 'checker_call_resolve.dewy'\nuse 'partition.jo'\n" + DRIVER + r'''
convert_error = false
cv_contract = 0
cv_effect_snapshot: Node[]
cv_type = (kind: TK, elem: int = 0, count: int = 0, flags: int = 0) -> int:
    t = types.len(); types.push(TypeInfo(kind=kind, elem=i32(elem), nargs=i32(count), flags=i32(flags))); t
cv_score = (a: int, t: int, bs: int[] = []):
    let bs = bs
    r = arg_cost_rest(a, t, bs)
    print("cost:{r}:{bs}")
cv_children = (n: int, xs: int[]): decl_children[n] = xs; nodes[n].nlist = i32(xs.len())
'''
MAIN = r'''main = ():
    prepare(); events = []
    x = cr_arg(.ident, T_INT)
    lit = cr_arg(.int_lit, T_INT, true)
    fl = cr_arg(.float_lit, T_FLOAT, true)
    cv_score(lit, T_INT)
    nodes[lit].ival = 128; cv_score(lit, T_INT); nodes[lit].ival = 0
    cv_score(lit, T_FLOAT); cv_score(fl, T_FLOAT)
    param = cv_type(.param, flags=1)
    cv_score(lit, param, [0]); cv_score(lit, param, [T_INT])
    cv_score(x, param, [0])
    cv_score(lit, cv_type(.secret, T_INT))
    # Context-sensitive branches, lambdas and optional values.
    hole = cr_arg(.hole); cv_score(hole, T_INT)
    lambda = cr_arg(.lambda)
    cv_score(lambda, cv_type(.fn_)); cv_score(lambda, param, [0])
    p = node(.param); nodes[p].a = 1; cv_children(lambda, [p])
    cv_score(lambda, cv_type(.fn_, count=1)); cv_score(lambda, param, [0])
    array = cr_arg(.array); cv_children(array, [lit, x])
    cv_score(array, cv_type(.array, T_INT))
    cv_score(array, cv_type(.array, param, flags=1), [0])
    cv_score(array, cv_type(.tuple, count=2))
    cv_score(array, cv_type(.tuple, count=1))
    cv_score(cr_arg(.none_lit), cv_type(.opt, T_INT))
    dot = cr_arg(.dotname); nodes[dot].name = 1
    cv_score(dot, cv_type(.enum_))
    # Branch scoring sees only literals/typed names, preserving hidden bindings.
    sym = syms.len(); syms.push(Sym(kind=.local, ref=1)); locals.push(Local(type=i32(T_INT)))
    name = cr_arg(.ident); nodes[name].name = i32(sym)
    bs: int[]
    print(branch_arg_cost(name, T_INT, bs))
    print(branch_arg_cost(name, T_INT, bs, [sym]))
    branch = node(.if_); nodes[branch].b = i32(lit); nodes[branch].c = i32(fl)
    print(branch_arg_cost(branch, T_INT, bs))
    block = node(.block); statement = node(.exprstmt); nodes[statement].a = i32(lit)
    cv_children(block, [statement]); print(branch_arg_cost(block, T_INT, bs))
    unary = node(.unary); nodes[unary].a = i32(lit)
    print(branch_arg_cost(unary, T_INT, bs))
    # String/refinement cold services return their own scores.
    str_sets.push(["x"])
    cv_score(x, T_STR)
    refine_active = true; cv_score(lit, cv_type(.refined, T_INT))
    # Finishing restores refinement state, invalidates paths and marks places.
    refine_arg_target = 77
    arg_finish_rest(x, T_FLOAT, false)
    assert(refine_arg_target == 77 and nodes[x].type == i32(T_FLOAT))
    nodes[x].flags |= 1
    path_narrows = 1
    arg_finish_rest(x, T_FLOAT, true)
    assert(partition_active)
    arg_finish_rest(hole, T_INT, false)
    assert(nodes[hole].type == i32(T_INT))
    bs = []; receiver = false
    print(call_mutable_cost(x, T_FLOAT, bs, receiver, true)); assert(receiver)
    effects_active = true; cv_contract = T_FLOAT
    effect_node = cr_arg(.ident, T_INT)
    cv_score(effect_node, T_FLOAT)
    assert(nodes[effect_node].type == i32(T_FLOAT))
    effects_active = false
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_convert_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_call_cost', 'checker_call_convert'),
                   doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')


def test_checker_call_convert_error(compiler, tmp_path):  # noqa: F811
    main = '''main = ():
    prepare(); convert_error = true
    a = cr_arg(.lambda); p = node(.param); nodes[p].a = 1; cv_children(a, [p])
    cv_score(a, cv_type(.fn_, count=1))
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=33,
                     extra_stems=('checker_call_cost', 'checker_call_convert'), doubles=DOUBLES, jo_doubles=JO)
    assert b'signature-error' in output


@pytest.mark.parametrize('setup,kind', [
    ('arg_finish_rest(x, T_INT, true)', 2),
    ('nodes[x].flags |= 1; nodes[x].aux2 = 103; arg_finish_rest(x, T_INT, false)', 3),
    ('nodes[x].flags |= 129; arg_finish_rest(x, T_FLOAT, true)', 4),
])
def test_checker_call_argument_errors(compiler, tmp_path, setup, kind):  # noqa: F811
    main = 'main = ():\n    prepare(); x = cr_arg(.ident, T_INT)\n    ' + setup + '\n'
    output = compare(compiler, tmp_path, False, DRIVER + main, status=34,
                     extra_stems=('checker_call_cost', 'checker_call_convert'), doubles=DOUBLES, jo_doubles=JO)
    assert f'argument-error:{kind}'.encode() in output
