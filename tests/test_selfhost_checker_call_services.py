"""Carved call services preserve routing, call type arguments and diagnostics."""
import re
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.test_selfhost_checker_call_convert import DRIVER as CONVERT_DRIVER, JO as CONVERT_JO, DOUBLES as CONVERT_DOUBLES

JO = dict(CONVERT_JO)
DOUBLES = {name: dict(pair) for name, pair in CONVERT_DOUBLES.items()}
EXTRA = {
    'expr.jo': r'''
enum IN:
    none_, len, arrdata, assert, fixed_abs
args_fit = (d: int, n: int) -> bool: false
bc_field = (recv: int, name: str, pos: int) -> int: 0
bc_ident = (name: str, pos: int) -> int: 0
breakpoint_call = (n: int) -> int: 0
call_collect_fns = (name: int, out: mut int[]): return
call_collect_module = (mod: int, name: int, out: mut int[]): return
call_collect_named = (name: int, mod: int, out: mut int[]): return
call_dispatch_error = (kind: int, n: int, name: int, callee: int, expected: int, rt: int, fname: int, et: int, tt: int): return
call_fixed_array_error = (n: int, name: int, t0: int, ii: int): return
call_numeric_member = (name: int) -> bool: false
call_search_name = (name: int) -> int: 0
call_totaldict_member = (name: int) -> bool: false
call_type_member_error = (callee: int, tt: int, fname: int) -> int: 0
callee_at = 0
check_copy = (n: int, receiver: int, t: int) -> int: 0
check_expr_in_module = (n: int, m: int, expected: int = 0) -> int: 0
check_soa_method = (n: int, recv: int, fname: int, args: int[], expected: int) -> int: 0
ci = (slot: int, s: str) -> int: 0
console_type = () -> int: 0
conversion = (n: int, to0: int, args: int[]) -> int: 0
dewy_arithmetic_call = (n: int, name: int, args: int[], expected: int) -> int: 0
dewy_byte_read = (n: int, callee: int, base: int, args: int[], expected: int) -> int: 0
dewy_console_call = (n: int, member: str, args: int[], expected: int) -> int: 0
dewy_len_check = (n: int, member: bool, t0: int, object: int): return
dewy_member_name = (callee: int, rt: int, fname: int, args: int[]) -> int: 0
dewy_method_call = (n: int, callee: int, method: int, args: int[], expected: int) -> int: 0
dewy_method_field = (t0: int) -> int: 0
dewy_quantity_name = (name: int) -> bool: false
dewy_range_ordered = (n: int, args: int[], expected: int) -> int: -1
dewy_range_tail_ordered = (n: int, args: int[], expected: int) -> int: -1
dewy_static_call = (n: int, t: int, j: int, args: int[], expected: int) -> int: 0
dewy_surface_check = (n: int, name: int): return
enum_from_int = (n: int, et: int, a: int) -> int: 0
expr_as_type = (e: int) -> int: 0
id_breakpoint = 506
id_len = 505
struct Intrinsic:
    name: str
    id: IN
    arr: bool
intrinsics: Intrinsic[] = [Intrinsic()]
last_checked = 0
method_str_set_key = (n: int, recv: int, rt: int, fname: int, args: mut int[], expected: int) -> int: 0
nargs_check = (n: int, nargs: int, lo: int, hi: int, name: str): return
program_fn_named = (name: int) -> bool: false
release_call = (n: int, args: int[], expected: int) -> int: 0
release_name = 0
relocate_call = (n: int, args: int[]) -> int: 0
relocate_name = 0
struct_ctor = (n: int, st_type: int, decl: int, args: int[], expected: int) -> int: 0
surface_hidden: int[]
synthetic_copy = (t: int, name: int, pos: int) -> bool: false
take_call = (n: int, args: int[]) -> int: 0
take_name = 0
takes_seq = (d: int) -> bool: false
to_int_word_limit = (a0: int) -> bool: false
value_call = (n: int, callee: int, args: int[], expected: int = 0) -> int: 0
variant_ctor = (n: int, et: int, vi: int, args: int[]) -> int: 0
''',
    'ast.jo': r'''
const NF_JUXT = 67108864
const NF_PRIVATE_COORD = 8192
const RANGE_EXHAUSTION = 32
id_chars = 501
id_find = 502
id_index_of = 504
id_rfind = 503
mk = (kind: NK, pos: int) -> int: 0
set_kid = (n: int, i: int, v: int): return
const NF_EXCL_FIRST = 67108864
const NF_SQUOTE = 8192
''',
    'types.jo': r'''
fixed_len = (t: int) -> int: 0
get_struct_inst = (decl: int, args: int[]) -> int: 0
int_policy = (t: int) -> int: 0
is_numeric = (t: int) -> bool: false
is_soa = (t0: int) -> bool: false
policy_int = (base: int, policy: int, pos: int) -> int: 0
simple_enum = (t: int) -> bool: false
''',
    'units.jo': r'''
dewy_quantity_call = (n: int, name: int, a: int, expected: int) -> int: 0
''',
    'check.jo': r'''
cur_mod = () -> int: 0
demand_name = (name: int): return
dewy_at = (pos: int) -> bool: false
ensure_global = (g: int, use_pos: int, in_flow: bool = false): return
jo_type_spelling = (nm: int, s: int, pos: int): return
method_modules = (t0: int) -> int[]: []
module_lookup = (m: int, name: int) -> int: 0
struct Module:
    is_prelude: bool
modules: Module[] = [Module()]
prelude: {int: int} = {}
resolve_alias = (d: int, targs: int[], use_pos: int) -> int: 0
runtime_fn = (name: str) -> int: 0
universe: {int: int} = {}
''',
    'dewy_methods.jo': r'''
dewy_type_method = (decl: int, name: int) -> int: 0
''',
    'effects.jo': r'''
effect_generic_argument = (tn: int) -> int: 0
''',
    'exact.jo': r'''
exact_int_result = (n: int, observe_unsigned: bool = false) -> int: 0
exact_type = (t0: int, pos: int) -> bool: false
''',
    'util.jo': r'''
intern = (s: str) -> int: 0
name_of = (id: int) -> str: ""
pos_in_lib = (p: int) -> bool: false
''',
    'reflection.jo': r'''
id_members = 507
members_array = (n: int, expected: int) -> int: 0
reflect_active = false
reflect_fields = (e: int) -> bool: false
reflect_member = (n: int) -> bool: false
reflect_members = (e: int) -> bool: false
reflect_name = (n: int): return
''',
    'ide.jo': r'''
ide_builtin_ref = (n: int, name: int): return
ide_complete_members = (t0: int): return
ide_complete_names = (): return
ide_complete_variants = (et: int): return
ide_field_ref = (p: int, name: int, d: int, i: int, type: int): return
ide_sentinel = 0
ide_sym_ref = (n: int, s: int): return
ide_variant_ref = (p: int, name: int, et: int, vi: int): return
''',
    'refine.jo': r'''
str_set_of = (t0: int) -> int: 0
''',
    'juxtapose.jo': r'''
juxt_chain_numeric = (c: int) -> bool: false
juxt_head_numeric = (r: int) -> bool: false
juxt_power = (p: int): return
juxt_product = (n: int): return
juxt_text = (h: int) -> str: ""
juxt_value_head = (n: int, head_kind: NK, head_text: str, t: int) -> bool: false
''',
    'string_domains.jo': r'''
string_domain_members = (n: int) -> bool: false
''',
}
for _file, _definitions in EXTRA.items():
    JO[_file] = JO.get(_file, '') + _definitions


def replace_service(file, name, definition):
    JO[file], count = re.subn(r'(?ms)^' + name + r' = .*?(?=^\S|\Z)', definition + '\n', JO[file])
    assert count == 1, name

replace_service('util.jo', 'name_of', 'name_of = (id: int) -> str: if id == 201: "__bcast_index" else if id == 202: "rational" else: ""')
replace_service('check.jo', 'runtime_fn', """runtime_fn = (name: str) -> int:
    cs_snapshot = nodes
    loop i in [0..256): nodes.push(Node())
    77
""")
replace_service('expr.jo', 'bc_ident', """bc_ident = (name: str, pos: int) -> int:
    cs_snapshot = nodes
    loop i in [0..256): nodes.push(Node())
    node(.ident)
""")
replace_service('expr.jo', 'bc_field', """bc_field = (recv: int, name: str, pos: int) -> int:
    cs_snapshot = nodes
    loop i in [0..256): nodes.push(Node())
    cs_built_field = node(.field)
    nodes[cs_built_field].a = i32(recv)
    cs_built_field
""")
replace_service('units.jo', 'bundled_word_rational_type', 'bundled_word_rational_type = (t: int) -> bool: t == T_INT')
replace_service('expr.jo', 'ci', 'ci = (slot: int, text: str) -> int: 100 + slot')
replace_service('expr.jo', 'call_dispatch_error', '''call_dispatch_error = (kind: int, n: int, name: int, callee: int, expected: int, rt: int, fname: int, et: int, tt: int): print("dispatch-error:{kind}"); exit(35)''')
replace_service('expr.jo', 'call_fixed_array_error', 'call_fixed_array_error = (n: int, name: int, t0: int, ii: int): print("fixed-array-error"); exit(35)')
replace_service('expr.jo', 'call_type_member_error', 'call_type_member_error = (callee: int, tt: int, fname: int) -> int: print("type-member-error"); exit(35); 0')
replace_service('expr.jo', 'dewy_member_name', 'dewy_member_name = (callee: int, rt: int, name: int, xs: int[]) -> int: name + 10')
replace_service('expr.jo', 'method_str_set_key', 'method_str_set_key = (n: int, recv: int, rt: int, name: int, xs: mut int[], expected: int) -> int: xs.push(recv); 0')
replace_service('expr.jo', 'value_call', 'value_call = (n: int, callee: int, xs: int[], expected: int = 0) -> int: events.push("value:{callee}:{xs}"); T_BOOL')
replace_service('expr.jo', 'variant_ctor', 'variant_ctor = (n: int, et: int, vi: int, xs: int[]) -> int: events.push("variant:{et}:{vi}"); T_BOOL')
replace_service('expr.jo', 'call_collect_named', 'call_collect_named = (name: int, mod: int, ds: mut int[]): ds.push(77); events.push("collect:{name}:{mod}")')
replace_service('expr.jo', 'expr_as_type', 'expr_as_type = (n: int) -> int: T_INT')
replace_service('check.jo', 'dewy_at', 'dewy_at = (pos: int) -> bool: true')
replace_service('effects.jo', 'effect_generic_argument', 'effect_generic_argument = (n: int) -> int: T_INT')
replace_service('refine.jo', 'str_set_of', 'str_set_of = (t: int) -> int: if types[t].bits == 93: 1 else: 0')
replace_service('reflection.jo', 'reflect_fields', 'reflect_fields = (n: int) -> bool: cs_fields_error')
replace_service('services.jo', 'cv_lookup', 'cv_lookup = (name: int) -> int: if name == 1: 1 else: 0')
replace_service('services.jo', 'cr_check', '''cr_check = (a: int, pt: int) -> int:
    events.push("check:{a}:{pt}")
    if cs_grow:
        cs_grow = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); syms.push(Sym()); fields.push(Field())
    nodes[a].type = i32(T_INT)
    last_checked = a
    T_INT
''')
JO['services.jo'] += '''cs_by_name = (n: int, name: int, mod: int, xs: int[], expected: int, ufcs: bool) -> int: events.push("by-name:{name}:{call_targs}"); T_FLOAT
cs_intrinsic = (n: int, ii: int, xs: int[], expected: int) -> int: events.push("intrinsic:{ii}"); T_FLOAT
'''
DOUBLES['checker_expr']['dewy'] += '''from p"services.jo" import (cs_by_name cs_intrinsic)
call_by_name=(n:int64 name:int64 mod:int64 xs:array<int64> expected:int64 ufcs:bool):>int64=>cs_by_name(n name mod xs expected ufcs)
check_intrinsic=(n:int64 ii:int64 xs:array<int64> expected:int64):>int64=>cs_intrinsic(n ii xs expected)
'''
DOUBLES['checker_expr']['jo'] += '''call_by_name = (n: int, name: int, mod: int, xs: int[], expected: int, ufcs: bool) -> int: cs_by_name(n, name, mod, xs, expected, ufcs)
check_intrinsic = (n: int, ii: int, xs: int[], expected: int) -> int: cs_intrinsic(n, ii, xs, expected)
'''
# The test drives dispatch only; conversion is separately differential-tested.
JO['checker_call_convert.dewy'] = '''arg_cost_rest=(a:int64 p:int64 @bs:array<int64>):>int64=>0
call_mutable_cost=(a:int64 p:int64 @bs:array<int64> @recv:bool receiver:bool):>int64=>0
arg_finish_rest=(a:int64 pt:int64 mutable:bool):>void=>{}
branch_arg_cost=(a:int64 p:int64 @bs:array<int64> hidden:array<int64>=[]):>int64=>0
'''
JO['checker_call_convert.jo'] = '''arg_cost_rest = (a: int, p: int, bs: mut int[]) -> int: 0
call_mutable_cost = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int: 0
arg_finish_rest = (a: int, pt: int, mutable: bool): return
branch_arg_cost = (a: int, p: int, bs: mut int[], hidden: int[] = []) -> int: 0
'''
# Explicitly import shared stand-ins, including newly introduced modules.
for _file in list(JO):
    if _file.startswith('checker_call_') or not _file.endswith('.jo'):
        continue
    JO[_file] = ("use 'driver.jo'\nuse 'node_store.dewy'\nuse 'checker_state.dewy'\nuse 'checker_types.dewy'\n"
                 + ''.join(f"use '{other}'\n" for other in JO if other.endswith('.jo')
                           and other != _file and not other.startswith('checker_call_'))) + JO[_file]

DRIVER = "use 'checker_call_convert.dewy'\n" + ''.join(f"use '{name}'\n" for name in EXTRA) + CONVERT_DRIVER + r'''
cs_fields_error = false
cs_snapshot: Node[]
cs_built_field = 0
cs_grow = false
cs_call = (callee: int, xs: int[] = []) -> int:
    n = node(.call); nodes[n].a = i32(callee); cv_children(n, xs); n
cs_prepare = ():
    prepare(); events = []
    syms = [Sym(), Sym(kind=.fns)]
'''
MAIN = r'''main = ():
    cs_prepare()
    callee = node(.ident); nodes[callee].name = 10
    n = cs_call(callee)
    assert(call_head(n, 0) == -1)
    cs_grow = true; nodes[callee].name = i32(id_breakpoint)
    assert(call_head(n, 0) == T_INT and not cs_grow)
    nodes[callee].name = 10
    assert(call_ident_special(n, 0) == -1)
    assert(call_value(n, 0) == T_BOOL)
    # Explicit call type arguments are restored after both syntax forms.
    base = node(.ident); nodes[base].name = 1
    applied = node(.typeapply); nodes[applied].a = i32(base); cv_children(applied, [1])
    n = cs_call(applied)
    call_targs = [T_BOOL]
    assert(call_typeapply(n, 0) == T_FLOAT and call_targs == [T_BOOL])
    indexed = node(.index); nodes[indexed].a = i32(base); nodes[indexed].b = 1
    n = cs_call(indexed)
    assert(call_index(n, 0) == T_FLOAT and call_targs == [T_BOOL])
    # Enum variants through shorthand and a type-valued receiver.
    et = cv_type(.enum_)
    dot = node(.dotname); nodes[dot].name = 2
    n = cs_call(dot)
    assert(call_dotname(n, et) == T_BOOL)
    tv = cv_type(.typeval, et)
    assert(call_member_type(n, dot, tv, 2, [], 0) == T_BOOL)
    recv = cr_arg(.ident, T_INT)
    rt = T_INT
    assert(call_member_prepare(n, dot, recv, rt, [], 0) == -1)
    str_sets.push(["word"]); types[et].bits = 93; rt = et
    assert(call_member_prepare(n, dot, recv, rt, [], 0) == -1 and rt == T_STR)
    fname = 2; xs: int[]
    assert(call_member_tail(n, dot, recv, rt, fname, xs, 0) == -1)
    assert(fname == 12 and xs == [recv])
    # A callable field, including arena growth during checking its callee.
    ft = cv_type(.fn_)
    fields = [Field(name=2, type=i32(ft))]
    structs = [StructInfo(nfields=1)]
    st = cv_type(.struct_)
    cs_grow = true
    assert(call_member_callable(n, dot, recv, st, 2, [], 0) == T_BOOL and not cs_grow)
    # Intrinsic filtering and the array-intrinsic path.
    intrinsics[0].id = .assert
    assert(call_name_intrinsic(n, 0) == -2)
    nodes[n].aux2 = i32(RANGE_EXHAUSTION)
    assert(call_name_intrinsic(n, 0) == 0)
    arr = cv_type(.array, T_INT); nodes[recv].type = i32(arr); nodes[recv].flags = 128
    intrinsics[0].arr = true; intrinsics[0].id = .len
    assert(call_name_array(n, 2, -1, [recv], 0, false, 0) == T_FLOAT)
    assert(call_name_early(n, 2, -1, [], 0, false) == -1)
    # A variable holding a function, then ordinary family collection.
    locals = [Local(), Local(type=i32(ft))]; syms[1] = Sym(kind=.local, ref=1)
    assert(call_name_sym(n, 1, -1, 1, [], 0, false, xs) == T_BOOL)
    ds: int[]
    assert(call_name_collect(n, 2, -1, [], 0, false, ds) == -1 and ds == [77])
    # Allocation during a service must precede acquisition of the node pointer.
    special = node(.ident); nodes[special].name = 201
    n = cs_call(special); add_flag(n, NF_PRIVATE_COORD)
    assert(call_head(n, 0) == T_INT and nodes[n].sym == 77)
    rational = node(.ident); nodes[rational].name = 202
    applied = node(.typeapply); nodes[applied].a = i32(rational)
    n = cs_call(applied)
    assert(call_typeapply(n, 0) == T_INT and nodes[n].a == i32(cs_built_field))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_services_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare(compiler, tmp_path, release, DRIVER + MAIN,
                     extra_stems=('checker_call_cost', 'checker_call_services'), doubles=DOUBLES, jo_doubles=JO)
    assert output.endswith(b'ok\n')
    assert b'by-name:1:[3]' in output and b'collect:2:-1' in output


@pytest.mark.parametrize('setup,message', [
    ('cs_fields_error = true; call_head(n, 0)', b'dispatch-error:1'),
    ('call_dotname(n, 0)', b'dispatch-error:3'),
    ('call_member_type(n, c, cv_type(.typeval), 2, [], 0)', b'type-member-error'),
    ('syms[1] = Sym(kind=.const_); xs: int[]; call_name_sym(n, 1, -1, 1, [], 0, false, xs)', b'dispatch-error:9'),
])
def test_checker_call_services_errors(compiler, tmp_path, setup, message):  # noqa: F811
    main = 'main = ():\n    cs_prepare(); c = node(.dotname); n = cs_call(c)\n    ' + setup + '\n'
    output = compare(compiler, tmp_path, False, DRIVER + main, status=35,
                     extra_stems=('checker_call_cost', 'checker_call_services'), doubles=DOUBLES, jo_doubles=JO)
    assert message in output

# Callable-value execution has its own differential; retain this driver's service.
JO['expr.jo'] = JO['expr.jo'].replace('value_call = ', 'value_call_double = ')
JO['checker_call_values.dewy'] = 'from p"expr.jo" import value_call_double\nvalue_call=(n:int64 callee:int64 args:array<int64> expected:int64=0):>int64=>value_call_double(n callee args expected)\n'
JO['checker_call_values.jo'] = "use 'expr.jo'\nvalue_call = (n: int, callee: int, args: int[], expected: int = 0) -> int: value_call_double(n, callee, args, expected)\n"
