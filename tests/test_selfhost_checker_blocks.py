"""Blocks and the statement dispatcher: sinks, value statements, `when`, sibling hooks, scopes and statement kinds match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_assigns import DRIVER as ASSIGNS
from tests.test_selfhost_checker_loops import DRIVER as LOOPS
from tests.test_selfhost_checker_vardecls import DRIVER as DECLS
from tests.test_selfhost_checker_resolve import compare

STEMS = ('checker_loops', 'checker_vardecls', 'checker_assigns', 'checker_exprstmts', 'checker_statements',
         'checker_for_loops', 'checker_returns', 'checker_blocks')


def hosts(driver):
    """A leaf driver's state and services, without its helpers."""
    return driver[len(LOOPS):driver.index('DEWY = 1 << 40')]


DRIVER = LOOPS + hosts(DECLS) + hosts(ASSIGNS) + r'''
db_body_mode = -1
db_arm = 0
db_bind = 0
db_discarding = true
db_exact = false
db_mode = -1
db_final = -1
db_declares = false
db_open = (b: int, want: bool) -> int:
    events.push("open:{b}:{want}:{db_body_mode}")
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
db_finish = (b: int, result: int, mode: int, n: int, want: bool) -> int:
    events.push("finish:{b}:{result}:{mode}:{n}:{want}")
    result + 100
db_reset = (mark: int):
    events.push("reset:{mark}")
    scopes.names.truncate(mark)
db_special = (s: int, code: int):
    events.push("special:{s}:{code}")
    if code == 2: nodes[s].kind = .test_
    if code == 4: scopes.names.push(s)
db_assign = (s: int) -> bool:
    events.push("declares:{s}")
    db_declares
db_error = (s: int, code: int):
    print(events)
    print("error:{s}:{code}")
    exit(19)
db_services = CheckerBlockHost(db_open, db_expand, db_direct, db_final_host, db_sibling, db_finish, db_reset, db_special, db_assign, db_error)
db_inputs = CheckerBlockInput(&nodes, &lists, &files, &scopes, &cx, &da_watch, &dv_block, &dv_index, &dv_flow_local, &db_body_mode, &db_arm, &db_bind, &db_discarding, &db_exact, &T_VOID, &T_NEVER, &db_services)
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
run = (b: int, expected: int = 0, want: bool = false):
    r = bk_block(b, expected, want)
    print("{b}:{r}:{nodes[b].type}:{nodes[b].aux}:{nodes[b].nlist}:{dv_block}:{dv_index}:{dv_flow_local}:{db_discarding}:{db_arm}:{scopes.names.len()}")
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
