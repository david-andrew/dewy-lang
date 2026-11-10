"""Recursive type syntax, binder restoration and service order match frozen Jo."""
import re
import subprocess

import pytest

from tests.driver_cache import build_driver
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_effect_double import effect_services
from tests.test_selfhost_type_constructors import DRIVER as CONSTRUCTORS

DRIVER = CONSTRUCTORS.split('main = ():')[0] + r'''
nodes: Node[] = [Node()]
lists: i32[]
names = ["", "z", "a", "overflow", "wrap"]
files: SrcFile[] = [SrcFile()]
fields: Field[]
variants: Variant[]
sets: str[][]
binders = RefineBindings()
refine = true
values_ok = false
pack_ok = false
grow = false
nested_type = 0
node_snapshot: Node[]
list_snapshot: i32[]
name_snapshot: str[]
intern_text = (s: str) -> int:
    loop i in [0..names.len()):
        if names[i] == s: return i
    names.push(s)
    names.len() - 1
label_input = TypeLabelInput(&names, &nodes, &lists, &files, intern_text)
label_binding = type_label_bind(&label_input)
optional = (t: int) -> int: int(tb_mk_opt(t))
set_of = (t: int) -> int: 0
set_type = (texts: str[]) -> int: T_STR
render_type = (t: int) -> str: "t{t}"
union_host = TypeUnionHost(optional, set_of, set_type, render_type, render_type, intern_text)
union_input = TypeUnionInput(&types, &structs, &args, &fields, &variants, &sets, &T_NEVER, &T_NONE, &union_host)
union_binding = type_union_bind(&union_input)
lookup_type = (n: int) -> CheckerTypeName:
    events.push("name:{n}:{binders.fields}:{binders.formals}:{binders.self}:{values_ok}:{pack_ok}")
    if grow:
        grow = false
        node_snapshot = nodes; list_snapshot = lists; name_snapshot = names
        loop i in [0..128): nodes.push(Node()); lists.push(0); names.push("padding")
        saved_formals = binders.formals
        saved_self = binders.self
        ct_resolve_type(nested_type)
        assert(binders.formals == saved_formals and binders.self == saved_self)
    CheckerTypeName(int(nodes[n].aux), int(nodes[n].ival))
policy_type = (t: int, p: int, pos: int) -> int:
    events.push("policy:{t}:{p}:{pos}")
    t
refinement = (n: int) -> int:
    events.push("refine:{n}:{binders.fields}:{binders.formals}:{binders.self}")
    T_INT
quantity = (n: int) -> int: T_FLOAT
ide = (n: int): events.push("ide:{n}")
effect_arg = (n: int) -> int:
    events.push("effect:{n}")
    T_BOOL
nominal = (t: int) -> int: t
fixed_arg = (n: int) -> bool: nodes[n].sval == 99
resolve_fixed_size_double = (n: int) -> int: 3
fixed = (t: int, count: int, pos: int) -> int: int(tb_mk_fixed(t, count))
instance = (d: int, ts: int[]) -> int:
    events.push("instance:{d}:{ts}")
    int(tb_mk_tuple(ts))
decimal = (pos: int) -> int: T_MATH_INT
word_rational = (pos: int) -> int: T_FLOAT
error = (kind: int, n: int, count: int):
    print("error:{kind}:{n}:{count}")
    exit(17)
record = (n: int, fs: int[]) -> int:
    ts: int[]
    loop f in fs: ts.push(int(nodes[f].type))
    events.push("record:{n}:{binders.fields}")
    int(tb_mk_tuple(ts))
validate_record = (t: int, pos: int): events.push("record-valid:{t}:{pos}:{binders.fields}")
nd = (t: int, pos: int) -> int: int(tb_mk_array(t))
soa = (t: int, pos: int) -> int: int(tb_mk_array(t))
map_decl = (n: int) -> int: 123
total_dict = (t: int, pos: int) -> int:
    events.push("total:{t}:{pos}")
    t
signature = (ps: int[], ret: int, mask: int, pos: int):
    events.push("signature:{ps}:{ret}:{mask}:{pos}:{binders.formals}:{binders.self}")
pack_count = (n: int) -> int:
    if n != 0 and nodes[n].ival < 0: return int(nodes[n].nlist)
    0
contract = (n: int, base: int, ps: int[], labels: int[], mask: int) -> int:
    events.push("contract:{n}:{base}:{ps}:{labels}:{mask}:{binders.formals}:{binders.self}")
    base
pack_error = (n: int, i: int, t: int, first: int):
    print("pack:{n}:{i}:{t}:{first}")
    exit(17)
resolve_input = CheckerResolveInput(&nodes, &lists, &types, &names, &binders, &refine, &values_ok, &pack_ok, &T_VOID, &T_INT)
resolve_binding = checker_resolve_bind(&resolve_input)
alias_resume = (d: int): events.push("resume:{d}")
alias_error = (k: int, n: int, p: int, c: int): error(k, n, c)
alias_atomic = () -> int: T_INT
alias_enter = (d: int, ts: int[]) -> CheckerAliasScope:
    events.push("alias:{d}:{ts}")
    CheckerAliasScope()
alias_leave = (scope: CheckerAliasScope): pass
alias_resolve = (n: int) -> int: int(ct_resolve_type(n))
alias_name = (n: int) -> str: names[n]
alias_note = (d: int, t: int): events.push("noted:{d}:{t}")
alias_host = CheckerAliasHost(alias_resume, alias_error, alias_atomic, alias_enter, alias_leave, alias_resolve, alias_name, policy_type, alias_note)
alias_binding = checker_alias_bind(&nodes, &lists, &alias_host)
node = (kind: NK, a: int = 0, value: int = 0, aux: int = 0, children: int[] = [], formals: int[] = []) -> int:
    n = nodes.len()
    nodes.push(Node(kind=kind, a=i32(a), ival=value, aux=i32(aux), pos=n))
    node_set_list(mut nodes, mut lists, n, children)
    node_set_list2(mut nodes, mut lists, n, formals)
    n
prepare = ():
    tb_init_types()
    binders.fields = [99]; binders.formals = [88]; binders.self = 77
    nested_type = node(.tfn)
main = ():
    prepare()
    it = node(.tname, 0, T_INT, 3)
    st = node(.tname, 0, T_STR, 3)
    bt = node(.tname, 0, T_BOOL, 0)
    grow = true
    z = node(.field, it); nodes[z].name = 1
    a = node(.field, node(.trefined)); nodes[a].name = 2
    rec = node(.trecord, 0, 0, 0, [z, a])
    rt = int(ct_resolve_type(rec))
    assert(not grow and node_snapshot[z].type == 0 and nodes[z].type == i32(T_INT))
    assert(nodes[a].type == i32(T_INT) and types[rt].kind == .tuple)
    assert(binders.fields == [99] and binders.formals == [88] and binders.self == 77)
    assert(ct_resolve_type(node(.tname, 0, T_BOOL, -7)) == T_BOOL)
    assert(ct_resolve_type(node(.tname, it, 1, -9)) == T_INT)
    assert(ct_resolve_type(node(.tquantity)) == T_FLOAT)
    assert(ct_resolve_type(node(.tname, 0, 0, 5)) == T_MATH_INT)
    assert(ct_resolve_type(node(.tname, 0, 0, 5, [it])) == T_FLOAT)
    assert(types[int(ct_resolve_type(node(.tname, 0, 0, 4, [it])))].kind == .secret)
    d = node(.typealias, it)
    assert(ct_resolve_type(node(.tname, 0, d, 1)) == T_INT)
    d2 = node(.typealias, it, 0, 0, [], [node(.tname, 0, 0, 1)])
    assert(ct_resolve_type(node(.tname, 0, d2, 1, [bt])) == T_INT)
    generic = node(.struct_, 0, 0, 0, [], [it, st])
    assert(types[int(ct_resolve_type(node(.tname, 0, generic, 2, [it, st])))].kind == .tuple)
    sized = node(.tname, 0, T_INT, 3, [it]); nodes[sized].sval = 99
    assert(types[int(ct_resolve_type(sized))].bits == 3)
    kinds: NK[] = [.tarray, .topt, .tptr]
    loop kind in kinds: print(ct_resolve_type(node(kind, it)))
    shaped = node(.tarray, it, 1, 2)
    print(ct_resolve_type(shaped))
    fixed_node = node(.tarray, it); nodes[fixed_node].b = i32(bt)
    assert(types[int(ct_resolve_type(fixed_node))].kind == .fixed)
    nd_node = node(.tarray, it, 0, 2); print(ct_resolve_type(nd_node))
    soa_node = node(.tarray, it); nodes[soa_node].flags = 131072; print(ct_resolve_type(soa_node))
    map = node(.tmap, it, 0, 1); nodes[map].b = i32(st); print(ct_resolve_type(map))
    print(ct_resolve_type(node(.ttuple, 0, 0, 0, [it, st])))
    assert(ct_resolve_type(node(.ttuple)) == T_VOID)
    assert(types[int(ct_resolve_binding(node(.ttuple, 0, 0, 7, [it, st])))].sign)
    print(ct_resolve_type(node(.tunion, 0, 0, 0, [it, st, bt])))
    pack = node(.tarray, 0, -1, 0, [it, it])
    pack_ok = true
    result = int(ct_resolve_result(pack))
    assert(pack_ok and types[result].sign)
    pack_ok = false
    nodes[it].flags = 1
    fn = node(.tfn, pack, 0, 0, [it, st], [z, a]); nodes[fn].sval = 1
    grow = true
    ft = int(ct_resolve_type(fn))
    assert(types[ft].kind == .fn_ and types[ft].mutmask == 1 and types[ft].sign)
    assert(not grow and not pack_ok and not values_ok)
    assert(binders.fields == [99] and binders.formals == [88] and binders.self == 77)
    nodes[fn].flags = 8192
    assert(types[int(ct_resolve_type(fn))].kind == .cfn)
    print(events)
    loop t in types: print("{int(t.kind)}:{t.elem}:{t.args}:{t.nargs}:{t.mutmask}:{t.st}:{t.sign}")
    print(args)
    print("ok")
'''


def compare(compiler, tmp_path, release, driver, status=0, extra_stems=(), doubles=None, jo_doubles=None):
    # doubles: {stem: {extension: text}}, modules standing in for compiler ones; jo_doubles:
    # {file: text}, Jo modules a Dewy module imports by file name, in both builds.
    # Supply the resolver's direct services to every derived leaf driver.
    arguments = getattr(jo_doubles, 'arguments', ())
    with_stderr = getattr(jo_doubles, 'with_stderr', False)
    if arguments:
        driver = jo_doubles.runtime_driver(driver)
    jo_doubles = dict(jo_doubles or {})
    # (a whole compiler supplies every service itself)
    for module, functions in () if 'main.jo' in jo_doubles else RESOLVE_JO.items():
        text = jo_doubles.get(module, "use 'driver.jo'\nuse 'checker_resolve.dewy'\n")
        if module == 'effects.jo' and 'struct EffectSummary:' in text:
            continue
        for name, definition in functions.items():
            if not re.search(r'(?m)^' + re.escape(name) + r'\s*=', text):
                text += definition + '\n'
        if "use 'checker_resolve.dewy'" not in text:
            text = "use 'checker_resolve.dewy'\n" + text
        if "use 'driver.jo'" not in text:
            text = "use 'driver.jo'\n" + text
        jo_doubles[module] = text
    outputs = []
    doubles = doubles or {}
    stems = ('node_store', 'source_types', 'checker_types', 'checker_state', 'checker_tokens',
             'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries',
             'type_intern', 'type_inference', 'type_constructors', 'type_labels',
             'type_unions', 'checker_alias', 'checker_resolve', 'checker_coerce') + tuple(doubles) + extra_stems
    for extension in ('dewy', 'jo'):
        modules = {}
        for stem in stems:
            if stem in doubles:
                text = doubles[stem][extension]
            else:
                text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            modules[f'{stem}.{extension}'] = effect_services(text, jo_doubles)
        for name, text in (jo_doubles or {}).items():
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
                # Real Dewy services may also import the leaf under comparison.
                # Switch those edges too, so the graph has one implementation.
                for stem in extra_stems:
                    text = text.replace(f'p"{stem}.dewy"', f'p"{stem}.jo"')
            modules[name] = effect_services(text, jo_doubles)
        modules['driver.jo'] = ''.join(f"use '{s}.{extension}'\n" for s in stems) + driver
        binary = build_driver(compiler, modules, release)
        ran = subprocess.run([binary, *arguments], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-6000:] + ran.stderr
        outputs.append(ran.stdout + ran.stderr if with_stderr else ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]



# The Jo services checker_resolve calls, routed to the driver.
RESOLVE_JO = {
    'check.jo': {
        'resolve_type_name': 'resolve_type_name = (tn: int) -> CheckerTypeName: lookup_type(tn)',
        'resolve_type_ide': 'resolve_type_ide = (tn: int): ide(tn)',
        'fixed_size_arg': 'fixed_size_arg = (tn: int) -> bool: fixed_arg(tn)',
        'fixed_size': 'fixed_size = (n: int) -> int: resolve_fixed_size_double(n)',
        'mk_fixed_checked': 'mk_fixed_checked = (e: int, n: int, pos: int) -> int: fixed(e, n, pos)',
        'type_param_defaults': 'type_param_defaults = (d: int, targs: int[]) -> int[]: targs',
        'resolve_type_error': 'resolve_type_error = (kind: int, tn: int, count: int): error(kind, tn, count)',
        'nd_of': 'nd_of = (t: int, pos: int) -> int: nd(t, pos)',
        'resolve_type_soa': 'resolve_type_soa = (et: int, pos: int) -> int: soa(et, pos)',
        'resolve_type_map_decl': 'resolve_type_map_decl = (tn: int) -> int: map_decl(tn)',
        'pack_result_count': 'pack_result_count = (tn: int) -> int: pack_count(tn)',
        'resolve_type_contract': 'resolve_type_contract = (tn: int, base: int, ps: int[], names: int[], mm: int) -> int: contract(tn, base, ps, names, mm)',
        'resolve_type_pack_error': 'resolve_type_pack_error = (tn: int, i: int, t: int, first: int): pack_error(tn, i, t, first)',
    },
    'types.jo': {
        'policy_int': 'policy_int = (base: int, policy: int, pos: int) -> int: policy_type(base, policy, pos)',
        'get_struct_inst': 'get_struct_inst = (decl: int, args: int[]) -> int: instance(decl, args)',
    },
    'refine.jo': {
        'resolve_refinement': 'resolve_refinement = (n: int) -> int: refinement(n)',
        'ref_validate_record': 'ref_validate_record = (t: int, pos: int): validate_record(t, pos)',
        'ref_field_shape': 'ref_field_shape = (tn: int, t: int, siblings: int[]) -> int: t',
        'total_dict_type': 'total_dict_type = (map: int, pos: int) -> int: total_dict(map, pos)',
        'ref_validate_signature': 'ref_validate_signature = (params: int[], ret: int, mask: int, pos: int): signature(params, ret, mask, pos)',
    },
    'units.jo': {
        'resolve_quantity_type': 'resolve_quantity_type = (n: int) -> int: quantity(n)',
    },
    'effects.jo': {
        'effect_argument': 'effect_argument = (tn: int) -> int: effect_arg(tn)',
    },
    'errors.jo': {
        'nominal_family': 'nominal_family = (t: int) -> int: nominal(t)',
    },
    'expr.jo': {
        'collection_array': 'collection_array = (n: int, t: int) -> int: t',
        'collection_check': 'collection_check = (n: int, expected: int) -> int: -1',
        'collection_value': 'collection_value = (n: int, t: int) -> int: t',
        'decimal_type': 'decimal_type = (pos: int) -> int: decimal(pos)',
        'word_rational_type': 'word_rational_type = (pos: int) -> int: word_rational(pos)',
        'dewy_record_schema': 'dewy_record_schema = (n: int, args: int[]) -> int: record(n, args)',
        'type_meet': 'type_meet = (ms: int[], pos: int) -> int: ms[0]',
        'bare_generic_set': 'bare_generic_set = (on: bool) -> bool: false',
    },
}

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_resolve_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER).endswith(b'ok\n')


@pytest.mark.parametrize('expression,error', [
    ('node(.int_lit)', 1),
    ('node(.ttuple, 0, 0, 7, [it, it])', 4),
    ('node(.tname, 0, T_INT, 3, [it, it])', 6),
    ('node(.tname, 0, node(.struct_), 2, [it])', 7),
    ('node(.tname, 0, 0, 5, [st])', 8),
])
def test_checker_resolve_errors(compiler, tmp_path, expression, error):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    it = node(.tname, 0, T_INT, 3)
    st = node(.tname, 0, T_STR, 3)
    ct_resolve_type({expression})
    assert(false)
'''
    assert compare(compiler, tmp_path, False, driver, 17).startswith(f'error:{error}:'.encode())


@pytest.mark.parametrize('duplicate', [False, True])
def test_checker_resolve_record_errors(compiler, tmp_path, duplicate):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    t = T_INT
    if not {'true' if duplicate else 'false'}: t = T_VOID
    it = node(.tname, 0, t, 3)
    field = node(.field, it)
    nodes[field].name = 1
    ct_resolve_type(node(.trecord, 0, 0, 0, [field, field]))
    assert(false)
'''
    error = 2 if duplicate else 3
    assert compare(compiler, tmp_path, False, driver, 17).startswith(f'error:{error}:'.encode())


@pytest.mark.parametrize('allowed,same', [(False, True), (True, False)])
def test_checker_resolve_pack_errors(compiler, tmp_path, allowed, same):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + f'''main = ():
    prepare()
    it = node(.tname, 0, T_INT, 3)
    st = node(.tname, 0, {'T_INT' if same else 'T_STR'}, 3)
    pack_ok = {'true' if allowed else 'false'}
    ct_resolve_type(node(.tarray, 0, -1, 0, [it, st]))
    assert(false)
'''
    assert compare(compiler, tmp_path, False, driver, 17).startswith(b'pack:')
