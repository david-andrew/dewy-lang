"""Instance cache publication and reentrant growth match the frozen Jo owner."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_signature import DRIVER as SIGNATURE, SIGNATURE_JO
from tests.test_selfhost_checker_resolve import compare

DRIVER = SIGNATURE.split('main = ():')[0] + r'''
functions: FnInst[] = [FnInst()]
instance_index: {FnInstanceKey: int}
contexts: FnCtx[]
context = -1
substitution_binding = type_substitute_bind(&inference_input)
result_pending_test = (n: int) -> int[]: []
result_candidate_test = (n: int, lit: bool) -> CheckerResultCandidate: CheckerResultCandidate()
result_host_test = CheckerResultHost(unused_one, result_pending_test, result_candidate_test)
result_binding_test = checker_results_bind(&nodes, &lists, &files, &result_host_test)
instance_nested = 0
instance_grow = false
instance_snapshot: FnInst[]
instance_decl_snapshot: DeclInfo[]
instance_cache_snapshot: {FnInstanceKey: int}
instance_poly = (d: int, ts: int[], pos: int) -> int: 1234
it_preflight = (d: int, pos: int): events.push("preflight:{d}:{pos}")
it_create = (d: int, pos: int) -> int:
    functions.push(FnInst(decl = i32(d), use_pos = pos))
    events.push("create:{d}")
    functions.len() - 1
instance_bad = (d: int, t: int, pos: int): print("bad:{pos}"); exit(19)
instance_depth = (d: int, pos: int): print("depth:{pos}"); exit(20)
it_load = (d: int, f: int, generic: bool):
    events.push("load:{d}:{f}:{generic}")
    if instance_grow:
        instance_grow = false
        instance_snapshot = functions
        instance_decl_snapshot = declarations
        instance_cache_snapshot = instance_index
        loop i in [0..128): functions.push(FnInst()); declarations.push(DeclInfo()); nodes.push(Node())
        ci_get_fn_inst(instance_nested, [], 100)
instance_pack = (f: int, n: int): events.push("pack:{f}:{n}")
instance_dewy = (pos: int) -> bool: true
it_validate = (f: int, sig: FnSig, pos: int): events.push("validate:{f}:{sig.generic}")
instance_clone = (n: int) -> int:
    nodes.push(nodes[n])
    nodes.len() - 1
it_attributes = (d: int, f: int, ts: int[], pos: int):
    assert(not declarations[cs_decl_info(d)].insts.contains(f))
    assert(instance_index.get(FnInstanceKey(d, ts)) == none)
    events.push("attributes:{f}")
instance_ensure = (f: int, pos: int):
    d = int(functions[f].decl)
    assert(declarations[cs_decl_info(d)].insts.contains(f))
    if functions[f].targs.len() > 0: assert(instance_index[FnInstanceKey(d, functions[f].targs)] == f)
    events.push("ensure:{f}:{pos}")
instance_input = CheckerInstanceInput(&nodes, &functions, &declarations, &instance_index, &contexts, &context, &T_VOID)
instance_binding = checker_instances_bind(&instance_input)
instance_decl = (generic: bool, ret: int) -> int:
    p = node(.param)
    d = node(.fn_, 0, 0, 0, [p])
    nodes[d].b = i32(node(.block))
    di = cs_decl_info(d)
    declarations[di].sig = FnSig(done = true, generic = generic, params = [if generic: tb_mk_param(0) else: T_INT], ret = i32(ret))
    d
main = ():
    prepare()
    sig_grow = false
    instance_nested = instance_decl(false, T_VOID)
    d = instance_decl(true, tb_mk_param(0))
    instance_grow = true
    f = ci_get_fn_inst(d, [T_INT], 7)
    assert(functions[f].ptypes == [T_INT] and functions[f].ret == i32(T_INT))
    assert(functions[f].body != nodes[d].b and functions[f].targs == [T_INT])
    assert(instance_snapshot[f].ret == 0 and instance_snapshot[f].body == 0)
    assert(instance_decl_snapshot[cs_decl_info(d)].insts.len() == 0 and instance_cache_snapshot.len() == 0)
    count = functions.len()
    assert(ci_get_fn_inst(d, [T_INT], 8) == f and functions.len() == count)
    v = int(tb_mk_var()); types[v].ref = i32(T_INT)
    assert(ci_get_fn_inst(d, [v], 9) == f and functions.len() == count)
    other = ci_get_fn_inst(d, [T_BOOL], 10)
    assert(other != f and functions[other].ret == i32(T_BOOL))
    contexts.push(FnCtx(inst = i32(f))); context = 0
    child = ci_get_fn_inst(d, [T_STR], 11)
    assert(functions[child].gdepth == 1)
    context = -1
    plain = ci_get_fn_inst(instance_nested, [], 12)
    assert(functions[plain].body == nodes[instance_nested].b)
    assert(ci_get_fn_inst(instance_nested, [], 13) == plain)
    assert(not events.contains("preflight:{instance_nested}:13"))
    nodes[instance_nested].c = 1
    assert(ci_get_fn_inst(instance_nested, [], 16) == plain)
    assert(events.contains("preflight:{instance_nested}:16"))
    nodes[instance_nested].c = 0
    inferred = instance_decl(false, 0)
    assert(functions[ci_get_fn_inst(inferred, [], 14)].ret == i32(T_VOID))
    assert(ci_get_fn_inst(node(.lambda), [], 15) == 1234)
    print(events)
    print("ok")
'''

# The Jo services checker_instances calls, routed to the driver.
INSTANCE_JO = {
    'poly_closure.jo': {
        'poly_inst': 'poly_inst = (decl: int, targs: int[], use_pos: int) -> int: instance_poly(decl, targs, use_pos)',
    },
    'check.jo': {
        'checker_state.dewy': "use 'checker_state.dewy'",
        'instance_preflight': 'instance_preflight = (decl: int, use_pos: int): it_preflight(decl, use_pos)',
        'instance_create': 'instance_create = (decl: int, use_pos: int) -> int: it_create(decl, use_pos)',
        'instance_bad_arg': 'instance_bad_arg = (decl: int, z: int, use_pos: int): instance_bad(decl, z, use_pos)',
        'instance_depth_error': 'instance_depth_error = (decl: int, use_pos: int): instance_depth(decl, use_pos)',
        'instance_load': 'instance_load = (decl: int, f: int, generic: bool): it_load(decl, f, generic)',
        'pack_written': 'pack_written = (f: int, tn: int): instance_pack(f, tn)',
        'dewy_at': 'dewy_at = (pos: int) -> bool: instance_dewy(pos)',
        'instance_validate': 'instance_validate = (f: int, sig: FnSig, use_pos: int): it_validate(f, sig, use_pos)',
        'instance_attributes': 'instance_attributes = (decl: int, f: int, zt: int[], use_pos: int): it_attributes(decl, f, zt, use_pos)',
        'ensure_ret': 'ensure_ret = (f: int, use_pos: int): instance_ensure(f, use_pos)',
    },
    'ast.jo': {
        'clone': 'clone = (n: int) -> int: instance_clone(n)',
    },
}
JO_DOUBLES = jo_doubles(INSTANCE_JO, SIGNATURE_JO)


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_instances_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_signature', 'type_substitute',
                                'checker_results', 'checker_instances'), jo_doubles=JO_DOUBLES).endswith(b'ok\n')


@pytest.mark.parametrize('statement,status', [
    ('ci_get_fn_inst(d, [int(tb_mk_var())], 901)', 19),
    ('contexts.push(FnCtx(inst = i32(f))); context = 0; functions[f].gdepth = 500; ci_get_fn_inst(d, [T_FLOAT], 902)', 20),
])
def test_checker_instances_reject_unbounded_requests(compiler, tmp_path, statement, status):  # noqa: F811
    compare(compiler, tmp_path, False, DRIVER.replace('    print(events)', '    ' + statement + '\n    print(events)'),
            status=status, extra_stems=('checker_signature', 'type_substitute',
                                       'checker_results', 'checker_instances'), jo_doubles=JO_DOUBLES)

from tests.selfhost_expr_double import isolate_sinks
isolate_sinks(JO_DOUBLES)
