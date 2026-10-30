"""Body result obligations: inferred results, declared results on every path, never and init."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[]
cx = 0
xe_body_type = 0
xe_never_skip = false
xe_void_end = false
xe_grow = false
xe_entry_host = (d: int, b: int): events.push("entry:{d}:{b}")
xe_init_host = (f: int, b: int): events.push("init:{f}:{b}")
xe_check_host = (f: int, d: int, b: int, infer: bool, want: bool, expected: int) -> int:
    events.push("check:{f}:{d}:{b}:{infer}:{want}:{expected}")
    if xe_grow:
        xe_grow = false
        loop i in [0..256): nodes.push(Node()); fns.push(FnInst()); ctxs.push(FnCtx()); types.push(TypeInfo())
    xe_body_type
# A statement's ival 1 marks it as ending every path.
xe_terminates_host = (s: int) -> bool:
    events.push("terminates:{s}")
    nodes[s].ival == 1
xe_default_host = (n: int) -> int:
    events.push("default:{n}")
    T_FLOAT
xe_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xe_never_skip_host = (d: int) -> bool: xe_never_skip
xe_throws_host = (f: int, b: int): events.push("throws:{f}:{b}")
xe_hint_host = (f: int, d: int): events.push("hint:{f}:{d}")
xe_void_end_host = (b: int, r: int) -> bool:
    events.push("void-end:{b}:{r}")
    xe_void_end
xe_error_host = (n: int, code: int, t: int, d: int):
    print(events)
    print("error:{n}:{t}:{d}:{code}")
    exit(19)
xe_services = CheckerBodyResultHost(xe_entry_host, xe_init_host, xe_check_host, xe_terminates_host, xe_default_host, xe_coerce_host, xe_never_skip_host, xe_throws_host, xe_hint_host, xe_void_end_host, xe_error_host)
xe_inputs = CheckerBodyResultInput(&nodes, &lists, &types, &files, &fns, &ctxs, &cx, &T_VOID, &T_NEVER, &xe_services)
xe_binding = checker_body_results_bind(&xe_inputs)
DEWY = 1 << 40
# A body whose last statement holds a value of type t (ends: never finishes).
body_of = (t: int, valued: bool, ends: bool = false, literal: bool = false) -> int:
    v = node(.ident); nodes[v].type = i32(t)
    if literal: nodes[v].flags = i32(256)
    s = node(.exprstmt, v)
    if ends: nodes[s].ival = 1
    b = node(.block, 0, 0, 0, [s])
    if valued: nodes[b].aux = 1
    b
function = (body: int, ret: int, infer: bool, kind: int = 0, dewy: bool = false) -> int:
    d = node(.fn_); nodes[d].name = 2
    if dewy: nodes[d].pos = DEWY + d
    fns.push(FnInst(body = i32(body), kind = i32(kind), decl = i32(d)))
    ctxs.push(FnCtx(inst = i32(fns.len() - 1), ret = i32(ret), infer_ret = infer))
    cx = ctxs.len() - 1
    fns.len() - 1
run = (f: int):
    xe_body(f, int(fns[f].decl))
    b = int(fns[f].body)
    print("{f}:{fns[f].ret}:{nodes[b].aux}:{ctxs[cx].ret}:{types[int(ctxs[cx].ret)].ref}")
prepare_results = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_results()
    xe_grow = true
    run(function(body_of(T_VOID, false), 0, false, 4))
    # Inferred results: from the value (a literal's default), from a never-ending end, or void.
    xe_body_type = T_INT
    run(function(body_of(T_INT, true), int(tb_mk_var()), true))
    run(function(body_of(T_INT, true, false, true), int(tb_mk_var()), true))
    run(function(body_of(T_VOID, false, true), int(tb_mk_var()), true))
    xe_never_skip = true
    run(function(body_of(T_VOID, false, true), int(tb_mk_var()), true))
    xe_never_skip = false
    run(function(body_of(T_VOID, false), int(tb_mk_var()), true))
    run(function(body_of(T_INT, true), T_VOID, true))
    run(function(body_of(T_INT, true), T_STR, true))
    run(function(body_of(T_INT, false, true), T_STR, true))
    # Declared results: the value coerces; an ending path; a void arm end; never functions.
    run(function(body_of(T_INT, true), T_STR, false))
    run(function(body_of(T_INT, false, true), T_STR, false))
    xe_void_end = true
    run(function(body_of(T_INT, false), T_STR, false))
    xe_void_end = false
    run(function(body_of(T_INT, false), T_VOID, false))
    run(function(body_of(T_INT, false, true), T_NEVER, false, 0, true))
    xe_body_type = T_NEVER
    run(function(body_of(T_INT, false), T_NEVER, false, 0, true))
    run(function(body_of(T_INT, false), T_STR, false))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_body_results_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_body_results',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xe_body_type = T_INT; run(function(body_of(T_INT, false), T_STR, true))', 1),
    ('xe_body_type = T_INT; f = function(body_of(T_INT, true), T_STR, true); fns[f].aux_void = true; run(f)', 2),
    ('xe_body_type = T_INT; run(function(body_of(T_INT, false), T_NEVER, false, 0, true))', 3),
    ('xe_body_type = T_INT; run(function(body_of(T_INT, false), T_STR, false))', 4),
])
def test_checker_body_results_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_results()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_body_results',))
    assert output.rstrip().endswith(f':{code}'.encode())
