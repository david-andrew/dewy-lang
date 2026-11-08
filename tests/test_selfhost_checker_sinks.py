"""General sink execution, growth and failure paths match frozen Jo."""
import re
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_value_calls import DRIVER as BASE, JO as BASE_JO, DOUBLES as BASE_DOUBLES
JO = dict(BASE_JO)
JO.pop("checker_sinks.dewy", None)
JO.pop("checker_sinks.jo", None)
DOUBLES = dict(BASE_DOUBLES)
DOUBLES["checker_exprstmts"] = {'dewy': "Sink:type=[\n    mode:int64=0\n    block:int64=0\n    root:int64=0 # (ARM: the BODY sink its values go to)\n    acc:int64=0 # the accumulator local, 0 until one is needed\n    loops:int64=0 # loop_serials.len() at the block\n    pending:int64=0 # sink_pending.len() at the block\n    decl:int64=0 # the accumulator's declaration, put first in the block when it closes\n    first:int64=0 # position of the first value before the end\n    returns:int64=0 # position of a `return value` in a BODY\n    finals:array<int64>=[] # BODY: the `if`/`match` nodes whose arms were ARM sinks\n    want:int64=0 # BODY of a written `:>(T T)`: how many values it gives (0: any number)\n    elem:int64=0 # ... and their type\n    count:int64=0 # ... the values expressed so far, each directly in the body's block\n    vague:int64=0 # ... where a value whose number is not known statically is (0: none)\n    direct:int64=0 # (the statement of the body's block being checked)\n    tuple:bool=false # BODY/BIND: several values with a static count are held in locals and given as `(T T)`, returned in place (no array); false: always pushed (a parallel body)\n    held:array<int64>=[] # ... the statements whose values are held so far (sink_splice says how) ...\n    hlocals:array<int64>=[] # ... and the locals holding them, one per value, in order\n    hcount:array<int64>=[] # ... how many of those each statement holds\n]\n", 'jo': 'struct Sink:\n    mode: int\n    block: int\n    root: int\n    acc: int\n    loops: int\n    pending: int\n    decl: int\n    first: int\n    returns: int\n    finals: int[]\n    want: int\n    elem: int\n    count: int\n    vague: int\n    direct: int\n    tuple: bool\n    held: int[]\n    hlocals: int[]\n    hcount: int[]\n'}
EXTRA = {'check.jo': {'LF_QUIET': 'const LF_QUIET = 65536',
              'SINK_ARM': 'const SINK_ARM = 3',
              'SINK_BIND': 'const SINK_BIND = 6',
              'SINK_BODY': 'const SINK_BODY = 2',
              'SINK_COLLECTOR': 'const SINK_COLLECTOR = 4',
              'SINK_NONE': 'const SINK_NONE = 0',
              'SINK_ONE': 'const SINK_ONE = 1',
              'SINK_VOID': 'const SINK_VOID = 5',
              'check_stmt': 'check_stmt = (s: int): return',
              'ctxs': 'ctxs: FnCtx[]',
              'cx': 'cx = -1',
              'has_value_return': 'has_value_return = (n: int) -> bool: false',
              'loop_serials': 'loop_serials: int[]',
              'sink_acc_name': 'sink_acc_name = () -> int: 0',
              'sink_arm_next': 'sink_arm_next = 0',
              'sink_body_mode': 'sink_body_mode = -1',
              'sink_close_body_error': 'sink_close_body_error = (i: int, first: int): return',
              'sink_close_count_error': 'sink_close_count_error = (i: int, b: int): return',
              'sink_error0': 'sink_error0 = (pos: int, vt: int, elem: int): return',
              'sink_error1': 'sink_error1 = (v: int): return',
              'sink_error2': 'sink_error2 = (v: int): return',
              'sink_error3': 'sink_error3 = (v: int): return',
              'sink_fn': 'sink_fn = -1',
              'sink_hold_error': 'sink_hold_error = (p: int, t: int, elem: int, parts: int[]): return',
              'sink_main_value': 'sink_main_value = (i: int, pos: int): return',
              'sink_no_tuple': 'sink_no_tuple = false',
              'sink_pack_error': 'sink_pack_error = (n: int, f: int): return',
              'sink_pending': 'sink_pending: int[]',
              'sink_pfinal': 'sink_pfinal: bool[]',
              'sink_splice': 'sink_splice: {int: int[]}',
              'sink_values_error': 'sink_values_error = (n: int, t: int): return',
              'sink_void_error': 'sink_void_error = (s: int, t: int): return',
              'sink_want_elem': 'sink_want_elem = 0',
              'sink_want_n': 'sink_want_n = 0',
              'sinks': 'sinks: Sink[]',
              'union_has_void': 'union_has_void = (t: int) -> bool: false'},
 'ast.jo': {'NF_STMT': 'const NF_STMT = 16'},
 'expr.jo': {'collection_array': 'collection_array = (n: int, t: int) -> int: t', 'collection_value': 'collection_value = (n: int, t: int) -> int: t', 'type_node_of': 'type_node_of = (t: int, pos: int) -> int: 0'},
 'util.jo': {'intern': 'intern = (s: str) -> int: 0'}}

EXTRA['check.jo']['use_sink'] = "use 'checker_exprstmts.dewy'"
for name in list(EXTRA['check.jo']):
    if '_error' in name:
        signature = EXTRA['check.jo'][name].split('):')[0]
        EXTRA['check.jo'][name] = signature + '): print("' + name + '"); exit(44)'
EXTRA['check.jo']['sink_close_count_error'] = '''sink_close_count_error = (i: int, b: int):
    events.push("count-check:{sinks[i].count}:{sinks[i].want}")
    if sinks[i].count != sinks[i].want or sinks[i].vague != 0: print("sink-close-count"); exit(44)
'''
EXTRA['check.jo']['sink_close_body_error'] = 'sink_close_body_error = (i: int, first: int): events.push("body-check")'
EXTRA['check.jo']['check_stmt'] = '''check_stmt = (n: int):
    sn_snapshot = nodes
    loop j in [0..128): nodes.push(Node())
    l = locals.len(); locals.push(Local(type=nodes[int(nodes[n].a)].type))
    nodes[n].sym = i32(l)
'''
EXTRA['expr.jo']['type_node_of'] = '''type_node_of = (t: int, pos: int) -> int:
    sn_snapshot = nodes
    loop j in [0..128): nodes.push(Node())
    n = mk(.ttuple, pos); nodes[n].type = i32(t); n
'''
for module, text in jo_doubles(EXTRA).items():
    JO[module] = JO.get(module, '') + text

def replace(module, name, definition):
    JO[module] = re.sub(r'(?m)^' + name + r' = [^\n]*(?:\n(?:    [^\n]*|[ \t]*))*', definition.rstrip() + '\n', JO[module])

replace('expr.jo', 'capture_value', r'''capture_value = (a: int, t: int, pre: mut int[]) -> int:
    sn_snapshot = nodes
    loop j in [0..128): nodes.push(Node())
    l = locals.len(); locals.push(Local(type=i32(t)))
    d = mk(.vardecl, nodes[a].pos); nodes[d].sym = i32(l); nodes[d].b = i32(a)
    pre.push(d)
    mk_ident_local(l, nodes[a].pos)
''')
replace('expr.jo', 'coerce', 'coerce = (a: int, t: int) -> int: nodes[a].type = i32(t); a')
# This test uses the real sink leaf, not the value-call driver's sink service.
JO['check.jo'] = re.sub(r'(?m)^sink_values_use = [^\n]*\n', '', JO['check.jo'])
DRIVER = BASE + r'''
sn_snapshot: Node[]
sn_stmt = (v: int) -> int:
    n = va_node(.exprstmt); nodes[n].a = i32(v); n
sn_prepare = ():
    prepare(); events = []
    fns.push(FnInst()); ctxs.push(FnCtx(inst=1, ret=i32(T_INT))); cx = 0
'''
MAIN = r'''main = ():
    sn_prepare()
    a = va_node(.int_lit, T_INT); b = va_node(.int_lit, T_INT)
    sa = sn_stmt(a); sb = sn_stmt(b); block = va_node(.block, 0, [sa, sb])
    assert(sink_body_kind(block, true, true, T_INT, false) == SINK_BODY)
    assert(sink_body_kind(block, false, false, T_INT, true) == SINK_VOID)
    assert(sink_body_kind(block, false, true, T_INT, true) == SINK_ONE)
    assert(not sink_written(0)); nodes[block].a = i32(a); assert(sink_written(block)); nodes[block].a = 0
    sink_open(block, SINK_ONE)
    assert(sink_root(0) == 0 and sink_close(block, T_INT) == T_INT and sinks.len() == 0)
    sink_open(block, SINK_BODY); sink_fn = 0
    sink_return(91); sink_return(92); assert(sinks[0].returns == 91); sinks[0].returns = 0
    arm = va_node(.block); branch = va_node(.if_); sink_arm(branch, arm)
    assert(sink_arm_next == arm and sinks[0].finals == [branch])
    sink_open(arm, SINK_ARM); assert(sink_root(1) == 0)
    sink_close(arm, T_INT); sinks[0].finals = []
    # Two direct values remain locals and become a statically typed tuple.
    sinks[0].direct = sa; sink_express(sa, T_INT, false, false)
    sinks[0].direct = sb; sink_express(sb, T_INT, false, true)
    assert(sinks[0].count == 2 and sink_pending == [sa, sb])
    t = sink_close(block, T_INT)
    assert(is_values(t) and types[t].nargs == 2 and nodes[block].aux == 1)
    assert(sinks.len() == 0 and sink_pending.len() == 0 and sink_pfinal.len() == 0)
    assert(fns[1].pack_k == 2)
    # BIND applies its expected types; a single final expression stays unchanged.
    want = mk_values([T_INT, T_INT]); sink_bind_expect = want
    block2 = va_node(.block, 0, [sa]); sink_open(block2, SINK_BIND)
    assert(sinks[0].elem == want and sink_bind_expect == 0)
    sinks[0].direct = sa; sink_express(sa, T_INT, false, true)
    assert(sink_close(block2, T_INT) == T_INT and kids(block2) == [sa])
    # A body forced to collect builds its accumulator across arena relocation.
    sink_no_tuple = true; block3 = va_node(.block, 0, [sa, sb]); sink_open(block3, SINK_BODY)
    assert(not sinks[0].tuple and not sink_no_tuple)
    sinks[0].direct = sa; sink_express(sa, T_INT, false, false)
    sinks[0].direct = sb; sink_express(sb, T_INT, false, true)
    t = sink_close(block3, T_INT)
    assert(tkind(t) == .array and kids(block3).len() == 4 and nodes[kid(block3, 0)].kind == .vardecl)
    # Pack consumers, static result declarations, and flow-statement unwrapping.
    sink_pack_site = a; sink_pack_call(a); assert(sink_pack_hit == a)
    sink_values_use(a, want); assert(sink_pack_hit == a)
    node_mark(spread_calls, b); sink_pack_site = 0; sink_pack_call(b)
    tn = va_node(.ttuple); nodes[tn].ival = 2; pack_written(1, tn); assert(fns[1].pack_n == 2)
    sink_pack_body(1); assert(sink_body_mode == SINK_BODY and sink_want_n == 2)
    block4 = va_node(.block); sink_open(block4, SINK_BODY)
    assert(sinks[0].want == 2 and sink_want_n == 0); sinks[0].count = 2
    sink_close(block4, T_INT)
    branch = va_node(.if_); st = sn_stmt(branch); arm = va_node(.block, 0, [st])
    nodes[branch].b = i32(va_node(.block)); sink_flow_stmt(branch); sink_unwrap_last(arm)
    assert(kid(arm, 0) == branch and has_flag(branch, NF_STMT))
    print(events)
    loop n in nodes: print("{int(n.kind)}:{n.a}:{n.b}:{n.aux}:{n.type}:{n.sym}:{n.flags}")
    print("ok")
'''
STEMS = ('checker_sinks', 'checker_values', 'checker_call_cost', 'checker_call_convert')

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_sinks_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')

@pytest.mark.parametrize('case,message', [
    ('sink_pack_call(va_call(2))', 'sink_pack_error'),
    ('sink_values_use(va_node(.tuple), T_INT)', 'sink_values_error'),
    ('sink_open(va_node(.block), SINK_ONE); sink_express(sn_stmt(va_node(.int_lit, T_INT)), T_INT, false, false)', 'sink_error1'),
    ('sink_open(va_node(.block), SINK_VOID); sink_express(sn_stmt(va_node(.int_lit, T_INT)), T_INT, false, false)', 'sink_void_error'),
    ('sink_open(va_node(.block), SINK_BIND); sink_count(0, sn_stmt(va_node(.int_lit, T_INT)), false)', 'sink_error3'),
])
def test_checker_sinks_errors(compiler, tmp_path, case, message):
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    sn_prepare()\n    ' + case + '\n    print("unreachable")\n',
                     status=44, extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO)
    assert message.encode() in output
