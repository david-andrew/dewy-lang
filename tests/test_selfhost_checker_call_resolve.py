"""Call resolution owns selection, bindings, defaults and finishing in Dewy."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVE, compare

# Stand-ins own arenas so direct Jo imports and driver services see the same state.
JO = {
    'ast.jo': r'''use 'driver.jo'
use 'node_store.dewy'
nodes: Node[] = [Node()]
lists: i32[]
decl_children: {int: int[]} = {}
dewy_param_kinds: {int: int[]} = {}
const NF_MUT = 1
const NF_CHECKED = 128
nkids = (d: int) -> int: int(nodes[d].nlist)
nkids2 = (d: int) -> int: int(nodes[d].nlist2)
kid = (d: int, i: int) -> int: (decl_children.get(d) ?? [])[i]
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags |= i32(f)
set_list = (n: int, xs: int[]): events.push("list:{n}:{xs}")
''',
    'types.jo': r'''use 'driver.jo'
use 'checker_types.dewy'
types: TypeInfo[] = [TypeInfo()]
T_VOID = 0
T_BOOL = 0
T_STR = 0
T_NEVER = 0
prune = (t: int) -> int: int(tu_prune(t))
tkind = (t: int) -> TK: types[prune(t)].kind
has_var = (t: int) -> bool: int(types[t].flags) & 1 != 0
type_eq = (a: int, b: int) -> bool: prune(a) == prune(b)
targ = (t: int, i: int) -> int: T_INT
''',
    'util.jo': r'''use 'source_types.dewy'
files: SrcFile[] = [SrcFile(is_dewy=true)]
pos_file = (p: int) -> int: 0
''',
    'check.jo': r'''use 'driver.jo'
use 'checker_state.dewy'
decl_infos: DeclInfo[] = [DeclInfo()]
fns: FnInst[] = [FnInst()]
decl_info = (d: int) -> int: int(nodes[d].aux)
get_fn_inst = (d: int, bs: int[], pos: int) -> int:
    let bs = bs
    events.push("instance:{d}:{bs}")
    if grow_instances:
        grow_instances = false
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo()); decl_infos.push(DeclInfo()); fns.push(FnInst())
    sig = decl_infos[decl_info(d)].sig
    ps: int[]
    loop p in sig.params: ps.push(subst_partial(p, bs))
    f = fns.len()
    fns.push(FnInst(decl=i32(d), ptypes=ps, ret=sig.ret, targs=bs))
    f
''',
    'expr.jo': r'''use 'driver.jo'
use 'checker_call_cost.dewy'
struct CallFailure:
    rejected: int[]
    last_err_arg: int
setting_site = 0
rational_module_found = -1
call_targs: int[]
place_method = 0
dewy_literal_method_name = 71
const AUX2_PARTIAL = -10
exact_family_name = (n: int) -> bool: true
exact_members_for = (ds: int[], n: int, xs: int[]) -> int[]:
    rational_module_found = -1
    ds + extra_family
written_int_param = (d: int, i: int) -> bool: nodes[d].sval == 1
can_coerce = (n: int, a: int, b: int) -> bool: a == b
ntype = (a: int) -> int: int(nodes[a].type)
is_lit = (a: int) -> bool: int(nodes[a].flags) & 256 != 0
unnamed = (a: int) -> int:
    if nodes[a].kind == .namedarg: return int(nodes[a].a)
    a
has_hole = (xs: int[]) -> bool:
    loop a in xs:
        if a != 0 and nodes[a].kind == .hole: return true
    false
comprehension_settle = (xs: int[]) -> bool:
    if not settle_once: return false
    settle_once = false
    events.push("settle")
    true
decl_in_prelude = (d: int) -> bool: nodes[d].mod != 0
exact_args = (cd: Cand) -> int: int(nodes[cd.decl].ival)
call_map_candidate = (d: int, xs: int[], cd: mut Cand, kinds: int[], ufcs: bool, recv: mut bool, failure: mut CallFailure) -> bool:
    cd.missing = true
    if nodes[d].sval == -1: failure.last_err_arg = 8; return false
    cd.args = []
    loop a in xs: cd.args.push(unnamed(a))
    loop cd.args.len() < nkids(d): cd.args.push(0)
    events.push("map:{d}:{cd.args}")
    true
call_type_arity = (name: int, d: int, ts: int[], failure: mut CallFailure): failure.last_err_arg = 9
call_reject_candidate = (cd: Cand, failed: int, failure: mut CallFailure): failure.rejected.push(failed); failure.last_err_arg = failed
call_rejection_text = (failure: mut CallFailure): events.push("rejections:{failure.rejected}")
call_tie_error = (n: int, name: int, xs: int[], cands: Cand[], best: int): events.push("ties:{best}")
call_no_candidate = (n: int, name: int, ds: int[], xs: int[], expected: int, ufcs: bool, recv: bool, failure: mut CallFailure) -> int:
    print(events); print("no-candidate:{failure.last_err_arg}:{recv}"); exit(31)
    0
call_decl_checks = (n: int, name: int, d: int, xs: int[], cd: Cand, np: int, ufcs: bool): events.push("picked:{d}")
expected_binds = (cd: mut Cand, expected: int, given: int[]): events.push("expected:{expected}:{given}")
lit_default = (a: int) -> int: T_INT
match_type = (p: int, a: int, bs: mut int[], depth: int) -> int:
    if tkind(p) == .param:
        bs[int(types[p].id)] = a
        return 0
    if p == a: return 0
    -1
subst_partial = (p: int, bs: mut int[]) -> int:
    if tkind(p) == .param:
        if bs[int(types[p].id)] != 0: return bs[int(types[p].id)]
    p
param_in_union = (p: int, i: int) -> bool: false
default_uses_params = (a: int, d: int, i: int) -> bool: nodes[a].kind == .ident
default_arg = (d: int, i: int, pt: int, given: int[] = [], captured: bool = false, targs: int[] = []) -> int:
    events.push("default:{i}:{pt}:{given}:{captured}:{targs}")
    a = node(.int_lit); nodes[a].type = i32(T_INT)
    a
capture_value = (a: int, pt: int, ss: mut int[]) -> int: ss.push(a); events.push("capture:{a}"); a
finish_partial = (n: int, ps: int[], mask: int, ret: int) -> int: events.push("partial:{ps}:{mask}"); ret
call_resolve_error = (kind: int, n: int, name: int, d: int, i: int, partial: bool): print(events); print("error:{kind}:{i}:{partial}"); exit(32)
call_ide_ref = (n: int, name: int, xs: int[], d: int, f: int): events.push("ide")
call_note_contracts = (n: int, f: int, d: int, partial: bool, closure: int): events.push("contracts:{partial}:{closure}")
call_warn_unsettled = (n: int, f: int, d: int): events.push("warn:{d}")
call_capture_block = (n: int, f: int, ss: mut int[]): events.push("capture-block:{ss}")
call_conversion_double = (a: int, p: int, bs: mut int[]) -> int:
    if nodes[a].ival == -1: return -1
    if tkind(p) == .param and nodes[a].type != 0: bs[int(types[p].id)] = int(nodes[a].type)
    1
call_mutable_double = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int:
    if receiver: recv = true
    0
''',
    'services.jo': r'''use 'driver.jo'
use 'checker_state.dewy'
cr_signature = (d: int) -> FnSig:
    events.push("signature:{d}")
    decl_infos[decl_info(d)].sig.done = true
    decl_infos[decl_info(d)].sig
cr_check = (a: int, pt: int) -> int:
    events.push("check:{a}:{pt}"); nodes[a].type = i32(T_INT); T_INT
cr_finish = (a: int, pt: int, mutable: bool): events.push("finish:{a}:{pt}:{mutable}:{place_method}")
cr_untyped = (xs: int[]): events.push("untyped:{call_targs}")
cr_context = (a: int) -> bool: nodes[a].kind == .lambda or nodes[a].kind == .hole
cr_mutable = (xs: int[], mask: int, pos: int): events.push("mutable:{mask}")
cr_order = (n: int, xs: int[], fin: int[]): events.push("order:{xs}:{fin}")
''',
    'member_replay.jo': "use 'driver.jo'\nmember_record = -1\nmember_candidates = (ds: int[]): events.push(\"members:{ds}\")\n",
    'units.jo': 'bundled_rational_type = (t: int) -> bool: false\nbundled_word_rational_type = (t: int) -> bool: false\n',
    'effects.jo': '''struct Contract:
    variables: int[]
effect_contracts: Contract[] = [Contract()]
callable_contract = (t: int) -> int: 0
callable_base = (t: int) -> int: t
mk_callable_contract = (t: int, row: int) -> int: t
''',
    'poly_closure.jo': '''use 'driver.jo'
poly_default_type = (d: int, i: int, bs: int[]) -> int: default_arg(d, i, 0)
poly_default_variant = (d: int, xs: int[]) -> int: d
cr_reference_snapshot: Node[]
poly_fnref = (c: int, f: int) -> int:
    cr_reference_snapshot = nodes
    loop i in [0..256): nodes.push(Node())
    c
''',
    'refine.jo': '''use 'driver.jo'
struct RefArrayCall:
    candidate: int
refine_active = false
ref_array_call_prepare = (d: int, xs: mut int[], ps: int[], written: int[]) -> RefArrayCall: RefArrayCall(1)
ref_sib_dict_call = (d: int, xs: mut int[], ps: int[]):
    pass
ref_array_call_finish = (n: int, prepared: RefArrayCall) -> int: T_BOOL
representation_type = (t: int) -> int: t
''',
    'dewy_methods.jo': "use 'driver.jo'\ndewy_is_method = (d: int) -> bool: nodes[d].sval == 2\n",
    'ide.jo': 'ide_on = false\n',
    'proofs.jo': 'proof_active = false\n',
    'warn_if.jo': 'wi_any = false\n',
    'directives.jo': 'dir_floats_any = false\n',
    'check_constant.jo': "use 'driver.jo'\ncc_any = false\ncc_call = (n: int, f: int, d: int) -> int: T_BOOL\n"
                         "cc_choose = (n: int, ds: int[], xs: int[][], ps: int[][]) -> int[]: []\n",
}

# Direct imports do not re-export names; stand-ins explicitly share their arenas.
for _name in JO:
    JO[_name] = ''.join(f"use '{other}'\n" for other in JO if other != _name) + (
        "use 'node_store.dewy'\nuse 'checker_state.dewy'\nuse 'checker_types.dewy'\n"
        "use 'source_types.dewy'\nuse 'type_inference.dewy'\n"
    ) + JO[_name]

DOUBLES = {
    'checker_expr': {
        'dewy': '''from p"services.jo" import (cr_check cr_finish cr_untyped)
check_expr=(a:int64 pt:int64):>int64=>cr_check(a pt)
finish_arg=(a:int64 pt:int64 mutable:bool):>void=>cr_finish(a pt mutable)
check_args_untyped=(xs:array<int64>):>void=>cr_untyped(xs)
''',
        'jo': "use 'services.jo'\ncheck_expr = (a: int, pt: int) -> int: cr_check(a, pt)\nfinish_arg = (a: int, pt: int, mutable: bool): cr_finish(a, pt, mutable)\ncheck_args_untyped = (xs: int[]): cr_untyped(xs)\n",
    },
    'checker_call_queries': {
        'dewy': '''from p"services.jo" import (cr_context cr_mutable cr_order)
ctx_dependent=(a:int64):>bool=>cr_context(a)
check_mutable_arguments=(xs:array<int64> mask:int64 pos:int64):>void=>cr_mutable(xs mask pos)
save_call_order=(n:int64 xs:array<int64> fin:array<int64>):>void=>cr_order(n xs fin)
''',
        'jo': "use 'services.jo'\nctx_dependent = (a: int) -> bool: cr_context(a)\ncheck_mutable_arguments = (xs: int[], mask: int, pos: int): cr_mutable(xs, mask, pos)\nsave_call_order = (n: int, xs: int[], fin: int[]): cr_order(n, xs, fin)\n",
    },
    'checker_signature': {
        'dewy': 'from p"checker_state.dewy" import FnSig\nfrom p"services.jo" import cr_signature\nfn_sig=(d:int64):>FnSig=>cr_signature(d)\n',
        'jo': "use 'checker_state.dewy'\nuse 'services.jo'\nfn_sig = (d: int) -> FnSig: cr_signature(d)\n",
    },
}

DRIVER = RESOLVE.split('main = ():')[0]
for declaration in ('nodes: Node[] = [Node()]', 'types: TypeInfo[] = [TypeInfo()]',
                    'lists: i32[]', 'files: SrcFile[] = [SrcFile()]',
                    'T_VOID = 0', 'T_BOOL = 0', 'T_STR = 0', 'T_NEVER = 0'):
    DRIVER = DRIVER.replace(declaration + '\n', '')
DRIVER = ''.join(f"use '{name}'\n" for name in JO) + DRIVER + r'''
grow_instances = false
settle_once = false
extra_family: int[]
cr_decl = (ps: int[], ntp: int = 0, generic: bool = false, mask: int = 0, defaults: int[] = []) -> int:
    ds: int[]
    loop i in [0..ps.len()):
        p = node(.param)
        if i < defaults.len(): nodes[p].b = i32(defaults[i])
        ds.push(p)
    d = node(.fn_); nodes[d].nlist = i32(ps.len()); nodes[d].nlist2 = i32(ntp)
    nodes[d].aux = i32(decl_infos.len())
    decl_children[d] = ds
    decl_infos.push(DeclInfo(sig=FnSig(done=true, params=ps, ret=i32(T_INT), ntp=i32(ntp), generic=generic, mutmask=i32(mask))))
    d
cr_arg = (kind: NK = .ident, t: int = 0, literal: bool = false) -> int:
    a = node(kind); nodes[a].type = i32(t)
    if literal: nodes[a].flags = 256
    a
cr_run = (ds: int[], xs: int[], expected: int = 0, closure: int = 0, partial: bool = false):
    n = node(.call)
    if partial: nodes[n].aux2 = i32(AUX2_PARTIAL)
    t = resolve_fn_call(n, 45, ds, xs, expected, closure, true)
    print("result:{t}:{nodes[n].kind}:{nodes[n].sym}:{nodes[n].aux}:{nodes[n].a}:{nodes[n].type}")
    print(events); events = []
'''

MAIN = r'''main = ():
    prepare(); events = []
    x = cr_arg(.ident, T_INT)
    d = cr_decl([T_INT])
    grow_instances = true
    member_record = 0; ide_on = true; proof_active = true
    cr_run([d], [x])
    assert(not grow_instances)
    member_record = -1; ide_on = false; proof_active = false
    # Prefer nongeneric then user definitions, then exact argument matches.
    g = cr_decl([T_INT], generic=true)
    lib = cr_decl([T_INT]); nodes[lib].mod = 1
    cr_run([g, lib, d], [x])
    other = cr_decl([T_INT]); nodes[other].mod = 1; nodes[other].ival = 2
    settle_once = true
    cr_run([lib, other], [x])
    assert(not settle_once)
    extra_family = [d]; rational_module_found = 0
    cr_run([lib], [x])
    # Literal inference, a context-dependent argument, explicit type args.
    p = types.len(); types.push(TypeInfo(kind=.param, flags=1, id=0))
    generic = cr_decl([p], 1, true)
    lit = cr_arg(.int_lit, 0, true)
    cr_run([generic], [lit])
    cr_run([generic], [cr_arg(.lambda)])
    call_targs = [T_INT]
    cr_run([generic], [x])
    assert(call_targs.len() == 0)
    # Defaults infer a generic parameter; earlier parameters require captures.
    dv = cr_arg(.bool_lit, T_BOOL)
    def = cr_decl([p], 1, true, defaults=[dv])
    cr_run([def], [])
    before = node(.ident); nodes[before].name = 0
    def = cr_decl([T_INT, T_INT], defaults=[0, before])
    cr_run([def], [x])
    # Mutable method context is restored after finishing the receiver.
    method = cr_decl([T_INT], mask=1); nodes[method].sval = 2; nodes[method].name = 99
    cr_run([method], [x])
    assert(place_method == 0)
    refine_active = true; decl_infos[decl_info(method)].sig.ret = i32(T_VOID)
    cr_run([method], [x])
    refine_active = false
    cr_run([d], [cr_arg(.hole)], partial=true)
    cr_run([d], [x], closure=x)
    cc_any = true; nodes[d].c = 1
    cr_run([d], [x])
    print("ok")
'''

# A module boundary double isolates the scoring/resolver leaf from conversion.
JO['checker_call_convert.dewy'] = r'''from p"expr.jo" import call_conversion_double
arg_cost_rest=(a:int64 p:int64 @bs:array<int64>):>int64=>call_conversion_double(a p @bs)
'''
JO['checker_call_convert.jo'] = "use 'expr.jo'\narg_cost_rest = (a: int, p: int, bs: mut int[]) -> int: call_conversion_double(a, p, bs)\n"

JO['checker_call_convert.dewy'] += r'''from p"expr.jo" import call_mutable_double
call_mutable_cost=(a:int64 p:int64 @bs:array<int64> @recv:bool receiver:bool):>int64=>call_mutable_double(a p @bs @recv receiver)
'''
JO['checker_call_convert.jo'] += "call_mutable_cost = (a: int, p: int, bs: mut int[], recv: mut bool, receiver: bool) -> int: call_mutable_double(a, p, bs, recv, receiver)\n"


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_resolve_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare(compiler, tmp_path, release, DRIVER + MAIN,
                     extra_stems=('checker_call_cost', 'checker_call_resolve'),
                     doubles=DOUBLES, jo_doubles=JO)
    assert output.endswith(b'ok\n')
    assert b'capture-block:' in output and b'partial:' in output
    assert b'untyped:[]' in output and b'settle' in output


@pytest.mark.parametrize('setup,status,message', [
    ('d = cr_decl([T_INT]); a = cr_arg(.int_lit, 0, true); nodes[a].ival = -1; cr_run([d], [a])', 31, b'no-candidate:1:false'),
    ('d = cr_decl([]); call_targs = [T_INT]; cr_run([d], [])', 31, b'no-candidate:9:true'),
    ('p = types.len(); types.push(TypeInfo(kind=.param, flags=1)); d = cr_decl([], 1, true); cr_run([d], [])', 32, b'error:5:0:false'),
    ('a = node(.ident); d = cr_decl([T_INT], mask=1, defaults=[a]); cr_run([d], [])', 32, b'error:3:0:false'),
])
def test_checker_call_resolve_errors(compiler, tmp_path, setup, status, message):  # noqa: F811
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    prepare(); events = []\n    ' + setup + '\n',
                     status=status, extra_stems=('checker_call_cost', 'checker_call_resolve'),
                     doubles=DOUBLES, jo_doubles=JO)
    assert message in output
