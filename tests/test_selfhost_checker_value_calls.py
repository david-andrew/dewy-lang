"""Value-call expansion and contextual hints match the frozen Jo implementation."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_values import DRIVER as BASE, JO as BASE_JO, DOUBLES
JO = dict(BASE_JO)
EXTRA = {'ast.jo': {'clear_flag': 'clear_flag = (n: int, f: int): return', 'set_kid': 'set_kid = (n: int, i: int, v: int): return'}, 'types.jo': {'fixed_len': 'fixed_len = (t: int) -> int: 0', 'telem': 'telem = (t: int) -> int: 0'}, 'check.jo': {'ValuesItem': 'struct ValuesItem:\n    count: int      # values it gives (1; k; -1 for an array of unknown length)\n    spread: bool    # a container spread with `...`\n    hidden: bool    # a binding or a call: how many it gives is not written here', 'cur_mod': 'cur_mod = () -> int: 0', 'method_modules': 'method_modules = (t0: int) -> int[]: []', 'node_mark': 'node_mark = (marks: mut bool[], n: int): return', 'sink_values_use': 'sink_values_use = (n: int, t: int): return', 'values_call_labels': 'values_call_labels = (v: int, hints: int): return', 'values_collect_fns': 'values_collect_fns = (name: int, ds: mut int[]): return', 'values_collect_module': 'values_collect_module = (mod: int, name: int, ds: mut int[]): return', 'values_count_label': 'values_count_label = (count: int): return', 'values_dynamic': 'values_dynamic = (v: int): return', 'values_expand_error0': 'values_expand_error0 = (c: int): return', 'values_expand_error1': 'values_expand_error1 = (c: int, t: int): return', 'values_expand_error2': 'values_expand_error2 = (items: int[], i: int): return', 'values_expand_error3': 'values_expand_error3 = (items: int[], dyn: int): return', 'values_expand_error4': 'values_expand_error4 = (items: int[], dyn: int, arity: int): return', 'values_group_error0': 'values_group_error0 = (c: int): return', 'values_hint_first': 'values_hint_first: int[]', 'values_hint_mark': 'values_hint_mark = 0', 'values_hint_pos': 'values_hint_pos: int[]', 'values_hits': 'values_hits: bool[]', 'values_internal_callee': 'values_internal_callee = (callee: int) -> bool: false', 'values_length_check': 'values_length_check = (src: int, k: int, pos: int) -> int: 0', 'values_shift_warning': 'values_shift_warning = (item: int, count: int): return'}, 'expr.jo': {'args_fit': 'args_fit = (d: int, n: int) -> bool: false', 'dewy_member_name': 'dewy_member_name = (callee: int, rt: int, fname: int, args: int[]) -> int: 0', 'finalize_literal': 'finalize_literal = (n: int) -> int: 0', 'map_args': 'map_args = (pnames: int[], has_default: bool[], args: int[], out: mut int[], kinds: int[] = [], explain: bool = true) -> str: ""', 'program_fn_named': 'program_fn_named = (name: int) -> bool: false', 'receiver_literal_hint': 'receiver_literal_hint = (recv: int, name: int, nargs: int, expected: int, pos: int) -> int: 0', 'takes_seq': 'takes_seq = (d: int) -> bool: false', 'type_receiver_at': 'type_receiver_at = 0'}, 'effects.jo': {'effect_generic_argument': 'effect_generic_argument = (tn: int) -> int: 0'}, 'dewy_methods.jo': {'dewy_methods': 'dewy_methods: DewyMethod[]', 'dewy_type_method': 'dewy_type_method = (decl: int, name: int) -> int: 0'}, 'reflection.jo': {'members_argument': 'members_argument = (a: int): return', 'members_named': 'members_named = (a: int) -> bool: false'}, 'util.jo': {'name_of': 'name_of = (id: int) -> str: ""'}, 'poly_closure.jo': {'poly_families': 'poly_families: PolyFamily[] = [PolyFamily()]'}, 'refine.jo': {'str_set_of': 'str_set_of = (t0: int) -> int: 0'}}
EXTRA['ast.jo'].update({
    'clear_flag': 'clear_flag = (n: int, f: int): nodes[n].flags &= ~i32(f)',
    'set_kid': 'set_kid = (n: int, i: int, v: int): xs = kids(n); xs[i] = v; set_list(n, xs)',
})
EXTRA['types.jo']['fixed_len'] = 'fixed_len = (t: int) -> int: int(types[t].bits)'
EXTRA['types.jo']['telem'] = 'telem = (t: int) -> int: int(types[t].elem)'
EXTRA['dewy_methods.jo']['DewyMethod'] = 'struct DewyMethod:\n    decl: int\n    reads: bool'
EXTRA['poly_closure.jo']['PolyFamily'] = 'struct PolyFamily:\n    decl: int'
EXTRA['check.jo'].update({
    'node_mark': 'node_mark = (marks: mut bool[], n: int):\n    if marks.len() <= n: marks.resize(n + 1)\n    marks[n] = true',
    'sink_values_use': 'sink_values_use = (n: int, t: int): events.push("sink:{n}:{t}")',
    'values_internal_callee': 'values_internal_callee = (n: int) -> bool: nodes[n].name == 999',
    'values_length_check': 'values_length_check = (src: int, k: int, pos: int) -> int: events.push("length:{k}"); mk(.exprstmt, pos)',
    'values_count_label': 'values_count_label = (count: int): events.push("count:{count}")',
    'values_shift_warning': 'values_shift_warning = (item: int, count: int): events.push("shift:{count}")',
})
for _name in list(EXTRA['check.jo']):
    if '_error' in _name or _name == 'values_dynamic':
        _signature = EXTRA['check.jo'][_name].split('):')[0]
        EXTRA['check.jo'][_name] = _signature + '): print("' + _name + '"); exit(43)'
for _module, _text in jo_doubles(EXTRA).items():
    JO[_module] = JO.get(_module, "") + _text
DRIVER = ''.join(f"use '{m}'\n" for m in EXTRA) + BASE
MAIN = r'''main = ():
    prepare(); events = []
    a = va_node(.int_lit, T_INT); b = va_node(.bool_lit, T_BOOL)
    pre: int[]
    assert(values_expand([a, b], pre, 0) == [a, b] and pre.len() == 0)
    # Hidden packs preserve argument order and capture before later reads.
    pair = mk_values([T_INT, T_INT])
    local = va_local(pair); node_mark(values_hits, local)
    effect = va_node(.call, T_INT); add_flag(effect, NF_CHECKED)
    va_grow = true
    parts = values_expand([effect, local, b], pre, 0)
    assert(parts.len() == 4 and pre == [effect] and not va_grow)
    assert(nodes[parts[1]].kind == .field and nodes[parts[2]].ival == 1)
    # Fixed and unknown-length containers, including forced arena relocation.
    fixed = cv_type(.fixed, T_INT); types[fixed].bits = 2
    spread = va_local(fixed); add_flag(spread, NF_SPREAD)
    va_ident_growth = true; pre = []
    parts = values_expand([spread], pre, 0)
    assert(parts.len() == 2 and not va_ident_growth and not has_flag(spread, NF_SPREAD))
    d = cr_decl([T_INT, T_INT]); candidates = [d]
    fn = va_sym(.fns, d); call = va_node(.call); nodes[call].a = i32(fn)
    spread = va_local(int(tb_mk_array(T_INT))); add_flag(spread, NF_SPREAD)
    parts = values_expand([spread], pre, call)
    assert(parts.len() == 2 and pre.len() == 1)
    # Consensus hints reject conflicts, mutable parameters, missing defaults.
    assert(fns_param_hint([d], 1, 2) == T_INT)
    e = cr_decl([T_INT, T_BOOL]); assert(fns_param_hint([d, e], 1, 2) == 0)
    mutd = cr_decl([T_INT], mask=1); assert(fns_param_hint([mutd], 0, 1) == 0)
    assert(fns_argument_hints([d], [a, b]) == [T_INT, T_INT])
    assert(fns_argument_hints([d, e], [a, b]) == [T_INT, 0])
    generic = cr_decl([T_INT], ntp=1); nodes[generic].nlist2 = 1
    assert(fns_argument_hints([generic], [a], 0, [T_BOOL, T_INT]) == [0])
    set_list(call, [a, b]); assert(values_argument_hints(call, 0) == [T_INT, T_INT])
    # Fast no-expansion path and grouping, with sink restoration through recursion.
    assert(values_call(call, 0) == -1)
    internal = va_node(.ident); nodes[internal].name = 999
    hidden = va_node(.call); nodes[hidden].a = i32(internal); assert(values_call(hidden, 0) == -1)
    group = va_node(.tuple, 0, [a, b]); nodes[group].aux = i32(TUPLE_VALUES)
    sink_pack_site = group
    t = values_group(group, 0)
    assert(is_values(t) and nodes[group].kind == .tuple and last_checked == group)
    nested = va_node(.tuple, 0, [a, b]); nodes[nested].aux = i32(TUPLE_VALUES)
    set_list(call, [nested]); sink_pack_site = 77
    assert(values_call(call, 0) == T_INT and nodes[call].kind == .block and sink_pack_site == 77)
    print(events)
    loop n in nodes: print("{int(n.kind)}:{n.a}:{n.b}:{n.type}:{n.flags}")
    print("ok")
'''
STEMS = ('checker_values', 'checker_value_calls', 'checker_call_cost', 'checker_call_convert')

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_value_calls_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')

@pytest.mark.parametrize('case,message', [
    ('x = va_local(T_INT); add_flag(x, NF_SPREAD); pre: int[]; values_expand([x], pre, 0)', 'values_expand_error1'),
    ('x = va_local(int(tb_mk_array(T_INT))); add_flag(x, NF_SPREAD); pre: int[]; values_expand([x], pre, 0)', 'values_expand_error3'),
    ('x = va_node(.namedarg); n = va_node(.tuple, 0, [x]); values_group(n, 0)', 'values_group_error0'),
    ('x = va_call(0); node_mark(values_hits, x); pre: int[]; values_expand([x], pre, 0)', 'values_dynamic'),
])
def test_checker_value_calls_errors(compiler, tmp_path, case, message):
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    prepare()\n    ' + case + '\n    print("unreachable")\n',
                     status=43, extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO)
    assert message.encode() in output
