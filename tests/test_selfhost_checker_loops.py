"""Loop statements, labels and jumps match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
ctxs: FnCtx[]
cx = 0
scopes = CheckerScope()
serials: int[]
serial_next = 0
labels: LoopLabel[]
jumps: NarrowJump[]
last = 0
xb_grow = false
xb_rewrite = false
xb_names = 0
xb_check = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{serials}")
    if xb_grow:
        xb_grow = false
        loop i in [0..256): nodes.push(Node()); ctxs.push(FnCtx()); types.push(TypeInfo())
    last = n
    if xb_rewrite:
        xb_rewrite = false
        nodes.push(nodes[n])
        last = nodes.len() - 1
    int(nodes[n].type)
xb_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
xb_narrow = (n: int, holds: bool): events.push("narrow:{n}:{holds}")
xb_source = (n: int) -> int:
    events.push("source:{n}")
    int(nodes[n].a)
xb_binding = (name: int, t: int, pos: int) -> int:
    events.push("binding:{name}:{t}:{pos}")
    scopes.names.push(name)
    77
xb_body = (b: int):
    events.push("body:{b}:{ctxs[cx].loop_depth}:{labels.len()}")
    loop i in [0..xb_names): scopes.names.push(i)
    xb_names = 0
    loop k in kids(b):
        if nodes[k].kind == .while_: xb_while(k)
        else: xb_jump(k)
xb_reset = (mark: int):
    events.push("reset:{mark}")
    scopes.names.truncate(mark)
xb_error = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
kids = (n: int) -> int[]:
    out: int[]
    loop i in [0..int(nodes[n].nlist)): out.push(int(lists[int(nodes[n].list) + i]))
    out
xb_services = CheckerLoopHost(xb_check, xb_coerce, xb_narrow, xb_source, xb_binding, xb_body, xb_reset, xb_error)
xb_inputs = CheckerLoopInput(&nodes, &types, &ctxs, &cx, &scopes, &serials, &serial_next, &labels, &jumps, &last, &T_BOOL, &xb_services)
xb_binding_done = checker_loops_bind(&xb_inputs)
typed = (k: NK, t: int, a: int = 0) -> int:
    n = node(k, a); nodes[n].type = i32(t); n
loop_of = (cond: int, body: int[], label: int = 0, let_name: int = 0) -> int:
    s = node(.while_, cond)
    nodes[s].b = i32(node(.block, 0, 0, 0, body))
    nodes[s].sval = i32(label)
    if let_name != 0:
        nodes[s].aux = 1
        nodes[s].name = i32(let_name)
    s
jump = (k: NK, label: int = 0) -> int:
    s = node(k); nodes[s].name = i32(label); s
show = (s: int):
    print("{s}:{nodes[s].a}:{nodes[s].sym}:{nodes[s].ival}:{ctxs[cx].loop_depth}:{serials}:{serial_next}:{labels.len()}:{scopes.names.len()}")
prepare_loops = ():
    prepare()
    ctxs.push(FnCtx(inst = 1, parent = -1)); ctxs.push(FnCtx(inst = 2, parent = 0))
    cx = 1
'''

MAIN = r'''
main = ():
    prepare_loops()
    opt = int(tb_mk_opt(T_INT))
    # A plain test: no narrowing; a type test, a none comparison and a not narrow.
    s = loop_of(typed(.ident, T_BOOL), [jump(.break_), jump(.continue_)])
    xb_while(s); show(s)
    s = loop_of(typed(.istype, T_BOOL), [])
    xb_names = 3
    xb_while(s); show(s)
    eq = typed(.binary, T_BOOL, typed(.ident, opt)); nodes[eq].op = 70; nodes[eq].b = i32(typed(.none_lit, T_NONE))
    xb_while(loop_of(eq, []))
    nodes[eq].op = 71
    xb_while(loop_of(eq, []))
    xb_rewrite = true
    xb_while(loop_of(typed(.not_, T_BOOL), []))
    # Labels: nested loops, jumps out of several, the label stack per context.
    inner = loop_of(typed(.ident, T_BOOL), [jump(.break_, 5), jump(.continue_, 6), jump(.break_)], 6)
    outer = loop_of(typed(.and_, T_BOOL), [inner, jump(.continue_, 5)], 5)
    xb_grow = true
    xb_while(outer); show(outer); show(inner)
    loop k in kids(int(nodes[inner].b)): show(k)
    # The same label in another context is another loop.
    labels.push(LoopLabel(context = 0, name = 9, depth = 4))
    xb_while(loop_of(typed(.ident, T_BOOL), [jump(.break_, 9)], 9))
    # `loop let`: an optional value, or one whose optional view is its source.
    s = loop_of(typed(.ident, opt), [], 0, 11)
    xb_while(s); show(s)
    src = typed(.ident, opt)
    s = loop_of(typed(.unwrap, T_INT, src), [], 0, 12)
    xb_while(s); show(s)
    loop j in jumps: print("{j.context}:{j.depth}")
    xb_enter(loop_of(0, [], 3)); xb_leave(node(.while_))
    print(labels.len())
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_loops_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_loops',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xb_while(loop_of(typed(.ident, T_INT), [], 0, 11))', 1),
    ('xb_while(loop_of(typed(.ident, int(tb_mk_array(T_INT))), []))', 2),
    ('xb_while(loop_of(typed(.range, T_BOOL), []))', 2),
    ('xb_jump(jump(.continue_))', 3),
    ('xb_while(loop_of(typed(.ident, T_BOOL), [jump(.break_, 4)], 5))', 4),
    ('xb_while(loop_of(typed(.ident, T_BOOL), [loop_of(typed(.ident, T_BOOL), [], 5)], 5))', 5),
])
def test_checker_loops_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_loops()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_loops',))
    assert output.rstrip().endswith(f':{code}'.encode())
