"""Blocks and the statement dispatcher: sinks, value statements, `when`, sibling hooks, scopes and statement kinds match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_assigns import DRIVER as ASSIGNS
from tests.test_selfhost_checker_conditionals import DRIVER as CONDITIONALS
from tests.test_selfhost_checker_literals import DRIVER as LITERALS
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.test_selfhost_checker_vardecls import DRIVER as DECLS
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

STEMS = ('checker_loops', 'checker_vardecls', 'checker_assigns', 'checker_exprstmts', 'checker_statements',
         'checker_for_loops', 'checker_returns', 'checker_conditionals', 'checker_literals', 'checker_blocks')


def hosts(driver):
    """A leaf driver's state and services, without its helpers."""
    return driver[len(LOOPS):driver.index('DEWY = 1 << 40')]


def leaf_hosts(driver, end):
    """A resolver-based leaf driver's state and services (locals come from the declarations')."""
    prefix = RESOLVER.split('main = ():')[0]
    return driver[len(prefix):driver.index(end)].replace('locals: Local[] = [Local()]\n', '')


LEAVES = LOOPS + hosts(DECLS) + hosts(ASSIGNS) + leaf_hosts(CONDITIONALS, 'DEWY = 1 << 40') + leaf_hosts(LITERALS, 'main = ():')
DRIVER = LEAVES + r'''
db_body_mode = -1
db_arm = 0
db_bind = 0
db_discarding = true
db_exact = false
db_mode = -1
db_final = -1
db_declares = false
# (mode >= 0: a sink opened; -1, -2 (wanting a value): a discarding block's mode, db_mode)
db_open = (b: int, mode: int) -> int:
    events.push("open:{b}:{mode}:{db_body_mode}:{db_arm}:{db_bind}")
    if mode >= 0: return mode
    db_body_mode = -1
    if db_mode >= 0: db_discarding = false
    db_arm = 0; db_bind = 0
    db_mode
db_expand = (b: int):
    events.push("expand:{b}")
    kept: int[]
    loop i in [0..int(nodes[b].nlist)):
        k = int(lists[int(nodes[b].list) + i])
        if nodes[k].kind != .when_: kept.push(k)
    node_set_list(mut nodes, mut lists, b, kept)
db_direct = (s: int): events.push("direct:{s}")
db_final_host = (b: int, i: int, expected: int, mode: int) -> int:
    events.push("final:{b}:{i}:{expected}:{mode}")
    db_final
db_sibling = (n: int, m: int, code: int):
    events.push("sibling:{n}:{m}:{code}")
    if code == 2: bk_stmt(n)
db_close = (b: int, result: int) -> int:
    events.push("close:{b}:{result}")
    result + 100
db_check = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{nodes[n].flags}")
    last = n
    if nodes[n].ival != 0: last = typed(.ident, int(nodes[n].type))
    int(nodes[n].type)
db_terminates = (s: int) -> bool:
    events.push("terminates:{s}")
    nodes[s].ival != 0
db_reset = (mark: int):
    events.push("reset:{mark}")
    scopes.names.truncate(mark)
db_special = (s: int, code: int):
    events.push("special:{s}:{code}:{nodes[s].flags}")
    if code == 2: nodes[s].kind = .test_
    if code == 4: scopes.names.push(s)
db_assign = (s: int) -> bool:
    events.push("declares:{s}")
    db_declares
db_error = (s: int, code: int):
    print(events)
    print("error:{s}:{code}")
    exit(19)
db_services = CheckerBlockHost(db_open, db_expand, db_direct, db_final_host, db_sibling, db_close, db_reset, db_special, db_assign, db_error, db_check, db_terminates)
db_inputs = CheckerBlockInput(&nodes, &lists, &files, &types, &last, &scopes, &cx, &da_watch, &dv_block, &dv_index, &dv_flow_local, &db_body_mode, &db_arm, &db_bind, &db_discarding, &db_exact, &T_VOID, &T_NEVER, &db_services)
db_bound = checker_blocks_bind(&db_inputs)
DEWY = 1 << 40
dewy_node = (k: NK, a: int = 0) -> int:
    n = node(k, a); nodes[n].pos = DEWY + n; n
block_of = (stmts: int[], flags: int = 0) -> int:
    b = dewy_node(.block)
    node_set_list(mut nodes, mut lists, b, stmts)
    nodes[b].flags = i32(flags)
    b
let_of = (name: int, t: int) -> int:
    s = dewy_node(.vardecl)
    nodes[s].b = i32(typed(.ident, t))
    nodes[s].name = i32(name)
    s
assign_of = (t: int, op: int = 47, lhs: NK = .ident) -> int:
    s = dewy_node(.assign, typed(lhs, t))
    nodes[int(nodes[s].a)].aux = 1
    nodes[s].b = i32(typed(.int_lit, t))
    nodes[s].op = i32(op)
    s
# A statement `if` on a condition with else-less (or else) bodies the conditional host checks.
if_of = (other: bool = false, flags: int = 0) -> int:
    n = dewy_node(.if_, typed(.ident, T_BOOL))
    nodes[n].b = i32(typed(.block, T_VOID))
    if other: nodes[n].c = i32(typed(.block, T_VOID))
    nodes[n].flags = i32(flags)
    n
run = (b: int, expected: int = 0, want: bool = false):
    r = bk_block(b, expected, want)
    print("{b}:{r}:{nodes[b].type}:{nodes[b].aux}:{nodes[b].nlist}:{dv_block}:{dv_index}:{dv_flow_local}:{db_discarding}:{db_arm}:{scopes.names.len()}:{literal_last}:{xf_scope.names.len()}")
    print("  {events}")
    events = []
prepare_blocks = ():
    prepare_loops()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_blocks()
    # Statements: declarations, assignments (declaring ones too), nested blocks, `if`, tests.
    db_arm = 5
    run(block_of([let_of(11, T_INT), assign_of(T_INT), block_of([assign_of(T_I32)]), dewy_node(.if_), dewy_node(.test_), dewy_node(.build_)]))
    db_declares = true
    run(block_of([assign_of(T_INT)]))
    db_declares = false
    tuple_set = assign_of(T_INT); nodes[int(nodes[tuple_set].a)].kind = .tuple
    run(block_of([tuple_set]))
    run(block_of([assign_of(T_INT, 48), assign_of(T_INT, 47, .field)]))
    checked = let_of(12, T_INT); nodes[checked].flags = i32(128)
    shaped = let_of(12, T_INT); nodes[shaped].aux2 = 1789
    run(block_of([checked, shaped, dewy_node(.reflect_scope)]))
    db_exact = true
    run(block_of([assign_of(T_INT, 48), assign_of(T_INT)]))
    db_exact = false
    # Value blocks: sinks opened and closed, the final value, loop setups, transparency.
    db_mode = 1
    db_final = T_INT
    run(block_of([let_of(13, T_INT), dewy_node(.exprstmt)]), T_INT, true)
    db_final = -1
    run(block_of([let_of(13, T_INT), dewy_node(.if_)]), 0, true)
    db_mode = -1
    run(block_of([dewy_node(.if_)], 131072), 0, true)
    run(block_of([dewy_node(.if_)], 131072 | 1073741824), 0, true)
    run(block_of([]), 0, true)
    t = block_of([dewy_node(.if_)]); nodes[t].aux = 5
    run(t)
    t = block_of([dewy_node(.if_)]); nodes[t].aux = 5
    run(t, 0, true)
    db_body_mode = 2; db_mode = 2; db_final = T_I32
    run(block_of([let_of(14, T_INT), dewy_node(.exprstmt)]), 0, true)
    db_mode = -1; db_final = -1
    run(block_of([dewy_node(.if_)], 8))
    # `when` expanded; sibling records followed and known.
    run(block_of([dewy_node(.when_), let_of(15, T_INT), dewy_node(.when_)]))
    da_watch.sibling_flow = 1
    dv_flow_next = 1
    run(block_of([let_of(16, T_INT), assign_of(T_INT)]))
    dv_flow_next = 0
    da_watch.sibling_flow = 0
    da_watch.sibling_known = 1
    run(block_of([let_of(17, T_INT), dewy_node(.test_)]))
    # `if` statements: checked by the conditional leaf and published, once checked
    # again whole by the host; `$expect` tests asked about while there are any; `if let`.
    da_watch.sibling_known = 0
    stmts = [if_of(), if_of(true), if_of(false, 128), if_of(false, 16), dewy_node(.iflet)]
    nodes[stmts[2]].type = i32(T_VOID)
    run(block_of(stmts))
    loop s in stmts: print("{s}:{nodes[s].type}:{nodes[s].flags}")
    da_watch.expectations = 1
    literal_exact = true
    run(block_of([if_of(), let_of(18, T_INT), if_of(true)]))
    da_watch.expectations = 0
    literal_exact = false
    # Value blocks' sinks and final values: bodies, Dewy places (comprehensions, arms,
    # bindings), discarding blocks; spawns, collected values, matches, void and never;
    # ends that terminate, solved variables.
    db_mode = -1; db_final = -1
    value = typed(.call, T_INT); nodes[value].ival = 1
    run(block_of([let_of(30, T_INT), dewy_node(.exprstmt, value)]), T_INT, true)
    run(block_of([dewy_node(.test_)]), 0, true)
    m = typed(.match_, T_VOID); nodes[m].flags = i32(16)
    run(block_of([dewy_node(.exprstmt, m)]), 0, true)
    run(block_of([dewy_node(.exprstmt, typed(.call, T_NEVER))]), 0, true)
    ends = dewy_node(.test_); nodes[ends].ival = 1
    run(block_of([ends]), 0, true)
    run(block_of([dewy_node(.exprstmt, typed(.call, T_INT))], 67108864), 0, true)
    run(block_of([dewy_node(.exprstmt, typed(.call, T_INT))], 1073741824), 0, true)
    db_final = T_I32
    loop b in [block_of([dewy_node(.exprstmt, typed(.call, T_INT))]), block_of([dewy_node(.exprstmt, typed(.call, T_INT))])]:
        db_arm = b
        run(b, 0, true)
        db_bind = b
        run(b, 0, true)
    db_arm = 0; db_bind = 0
    jo = block_of([node(.exprstmt, typed(.call, T_INT))]); nodes[jo].pos = 0
    run(jo, 0, true)
    loop mode in [2, 3, 6]:
        db_body_mode = mode
        run(block_of([dewy_node(.exprstmt, typed(.call, T_INT))]), 0, true)
    db_body_mode = -1
    db_final = -1
    db_mode = 0
    run(block_of([dewy_node(.exprstmt, typed(.call, T_INT))], 8), 0, true)
    run(block_of([dewy_node(.test_)], 8))
    db_mode = -1
    types.push(TypeInfo(kind = .var, flags = i32(1), ref = i32(T_INT))); solved = types.len() - 1
    run(block_of([dewy_node(.exprstmt, typed(.call, solved))]), 0, true)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_blocks_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(block_of([dewy_node(.fn_)]))', 1),
    ('run(block_of([dewy_node(.import_)]))', 1),
    ('run(block_of([dewy_node(.int_lit)]))', 2),
    ('run(block_of([if_of(), dewy_node(.struct_)]))', 1),
    ('s = assign_of(T_INT, 48); spawned = typed(.call, T_INT); nodes[spawned].aux2 = 17; nodes[s].b = i32(spawned); run(block_of([s]))', 3),
])
def test_checker_blocks_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_blocks()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(f':{code}'.encode())
