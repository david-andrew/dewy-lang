"""Body lifetime, return exposure and diagnostic ancestry under nested growth."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_instances import DRIVER as INSTANCES
from tests.test_selfhost_checker_resolve import compare

DRIVER = INSTANCES.split('main = ():')[0] + r'''
body_locals: Local[] = [Local()]
trail: int[] = [99]
trail_names: str[] = ["outside"]
trail_fns: int[] = [99]
scopes = CheckerScope(names = [7], syms = [7], prev = [0], top = [0])
definite_decls: int[]
exposures = 0
skipped_never = false
nested_body = 0
outer_body = 0
body_grow = false
body_snapshot: FnInst[]
context_snapshot: FnCtx[]
body_lookup = (f: int) -> int:
    loop i in [0..contexts.len()):
        if contexts[i].inst == f: return i
    -1
body_error = (f: int, pos: int): print("recursive:{pos}"); exit(21)
body_restore = (f: int): events.push("restore:{f}")
body_measure = (phase: int, f: int) -> int:
    assert(phase == 1)
    events.push("measure:{f}")
    f
body_unmeasure = (saved: int): events.push("unmeasure:{saved}")
body_decimal = (f: int) -> bool: functions[f].kind == 77
body_decimal_check = (f: int):
    events.push("decimal:{f}")
    cb_check_body_now(f)
body_force = (d: int, f: int):
    assert(functions[f].state == 1)
    events.push("force:{f}:{context}")
body_type_params = (d: int, ts: int[]):
    assert(contexts[context].floor == scopes.names.len())
    scopes.names.push(d)
body_local = (nm: int, t: int, pos: int) -> int:
    body_locals.push(Local(name = i32(nm), type = i32(t), owner = contexts[context].inst))
    scopes.names.push(nm)
    body_locals.len() - 1
body_skip = (d: int) -> bool: nodes[d].aux == 99
body_reset = (mark: int): scopes.names.resize(mark)
body_infer = (f: int, d: int):
    assert(contexts[context].infer_ret and types[int(contexts[context].ret)].kind == .var)
    events.push("infer:{f}")
body_expression = (f: int, d: int):
    assert(functions[f].state == 1 and contexts[context].inst == f)
    if functions[f].targs.len() == 0: assert(trail.len() == 0)
    else: assert(trail_fns[trail_fns.len() - 1] == f)
    assert(body_locals[functions[f].params[0]].flags == 3)
    events.push("expression:{f}:{context}:{trail}:{trail_names}")
    if body_grow:
        body_grow = false
        body_snapshot = functions; context_snapshot = contexts
        saved = context
        saved_scopes = scopes.names
        saved_trail = trail
        loop i in [0..128): functions.push(FnInst()); nodes.push(Node()); body_locals.push(Local())
        # Force context capacity growth without retaining extra active contexts.
        loop i in [0..128): contexts.push(FnCtx())
        contexts.resize(saved + 1)
        cb_check_fn_body(nested_body)
        assert(context == saved and contexts[context].inst == f)
        assert(scopes.names == saved_scopes and trail == saved_trail)
    if contexts[context].infer_ret:
        tu_unify(int(contexts[context].ret), T_INT)
        cb_ensure_ret(f, 70)
        assert(functions[f].ret == i32(T_INT))
    else: functions[f].ret = contexts[context].ret
body_finalize = (f: int, vars0: int, binds0: int, exposed0: int, da_mark: int):
    assert(functions[f].state == 1 and contexts[context].inst == f)
    assert(vars0 <= var_counter and binds0 <= binds and exposed0 <= exposures and da_mark == 0)
    events.push("finalize:{f}")
body_host = CheckerBodyHost(instance_pack, instance_dewy, body_lookup, body_error, body_restore, body_measure, body_unmeasure, body_decimal, body_decimal_check, body_force, body_type_params, body_local, body_skip, body_reset, body_infer, body_expression, body_finalize)
body_input = CheckerBodyInput(&nodes, &lists, &types, &functions, &contexts, &body_locals, &names, &trail, &trail_names, &trail_fns, &scopes, &definite_decls, &context, &var_counter, &binds, &exposures, &T_VOID, &T_NEVER, &skipped_never, &body_host)
body_binding = checker_bodies_bind(&body_input)
body_fn = (generic: bool, ret: int) -> int:
    d = instance_decl(false, ret)
    nodes[cs_kid(d, 0)].flags = 1
    nodes[cs_kid(d, 0)].name = 1
    nodes[d].name = 2
    functions.push(FnInst(decl = i32(d), body = nodes[d].b, ret = i32(ret), ptypes = [T_INT], targs = if generic: [T_INT] else: [], use_pos = 123))
    functions.len() - 1
main = ():
    prepare()
    contexts.push(FnCtx(inst = 0)); context = 0
    nested_body = body_fn(false, T_VOID)
    outer_body = body_fn(true, 0)
    body_grow = true
    cb_check_fn_body(outer_body)
    assert(context == 0 and contexts.len() == 1 and scopes.names == [7])
    assert(trail == [99] and trail_names == ["outside"] and trail_fns == [99])
    assert(functions[outer_body].state == 2 and functions[nested_body].state == 2)
    assert(body_snapshot[outer_body].state == 1 and body_snapshot[outer_body].ret == 0)
    assert(context_snapshot.len() == 2 and functions[outer_body].ret == i32(T_INT))
    count = events.len()
    cb_check_fn_body(outer_body)
    assert(events.len() == count + 1, "restore precedes the checked guard")
    count = events.len(); cb_ensure_ret(outer_body, 71); assert(events.len() == count)
    ext = body_fn(false, 0); nodes[int(functions[ext].decl)].flags = 4
    cb_check_fn_body(ext)
    assert(functions[ext].state == 2 and functions[ext].ret == i32(T_NEVER) and not skipped_never)
    skipped = body_fn(false, 0); nodes[int(functions[skipped].decl)].aux = 99
    cb_check_fn_body(skipped)
    assert(skipped_never and functions[skipped].state == 2)
    decimal = body_fn(false, T_INT); functions[decimal].kind = 77
    cb_check_fn_body(decimal)
    assert(functions[decimal].state == 2 and context == 0 and scopes.names == [7])
    recursive = body_fn(false, 0); functions[recursive].state = 1
    cb_ensure_ret(recursive, 72)
    assert(functions[recursive].ret == i32(T_VOID) and functions[recursive].aux_void)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_bodies_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_signature', 'type_substitute', 'checker_results',
                                'checker_instances', 'checker_bodies')).endswith(b'ok\n')


def test_checker_bodies_recursive_error(compiler, tmp_path):  # noqa: F811
    driver = DRIVER.replace('    print(events)', '''    bad = body_fn(false, 0)
    functions[bad].state = 1
    nodes[int(functions[bad].decl)].b = i32(node(.return_, node(.int_lit)))
    cb_ensure_ret(bad, 903)
    print(events)''')
    compare(compiler, tmp_path, False, driver, status=21,
            extra_stems=('checker_signature', 'type_substitute', 'checker_results',
                         'checker_instances', 'checker_bodies'))
