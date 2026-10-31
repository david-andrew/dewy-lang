"""Recursive type syntax, binder restoration and service order match frozen Jo."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
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
fixed_size = (n: int) -> int: 3
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
resolve_host = CheckerResolveHost(lookup_type, policy_type, refinement, quantity, ide, effect_arg, nominal, fixed_arg, fixed_size, fixed, instance, decimal, word_rational, error, record, validate_record, nd, soa, map_decl, total_dict, signature, pack_count, contract, pack_error)
resolve_input = CheckerResolveInput(&nodes, &lists, &types, &names, &binders, &refine, &values_ok, &pack_ok, &T_VOID, &T_INT, &resolve_host)
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


def compare(compiler, tmp_path, release, driver, status=0, extra_stems=(), doubles=None):
    # doubles: {stem: {extension: text}}, modules standing in for compiler ones.
    outputs = []
    doubles = doubles or {}
    stems = ('node_store', 'source_types', 'checker_types', 'checker_state', 'checker_tokens',
             'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries',
             'type_intern', 'type_inference', 'type_constructors', 'type_labels',
             'type_unions', 'checker_alias', 'checker_resolve') + tuple(doubles) + extra_stems
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            if stem in doubles:
                text = doubles[stem][extension]
            else:
                text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])], capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-6000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


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
