"""Local constants, dropped values, `when` and `defer` match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_exprstmts import DRIVER as EXPRSTMTS
from tests.test_selfhost_checker_resolve import compare

STEMS = ('checker_exprstmts', 'checker_statements')
DRIVER = EXPRSTMTS + r'''
globals: Global[] = [Global()]
ctxs: FnCtx[]
cx = -1
st_refine_on = false
st_truth_value = false
st_mutable = false
st_grow = false
st_resolve_host = (n: int) -> int:
    events.push("resolve:{n}")
    T_I32
st_clone_host = (n: int) -> int:
    events.push("clone:{n}")
    if st_grow:
        st_grow = false
        loop i in [0..256): nodes.push(Node()); globals.push(Global()); ctxs.push(FnCtx()); lists.push(0)
    nodes.push(nodes[n])
    nodes.len() - 1
st_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    nodes.push(nodes[n])
    es_last_at = nodes.len() - 1
    int(nodes[n].type)
st_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n
st_literal_host = (n: int) -> int:
    events.push("literal:{n}")
    T_INT
st_bind_host = (name: int, g: int): events.push("bind:{name}:{g}")
st_truth_host = (n: int) -> bool:
    events.push("truth:{n}")
    st_truth_value
st_statement_host = (n: int): events.push("statement:{n}:{int(nodes[n].kind)}")
st_block_host = (n: int): events.push("block:{n}")
st_mutable_host = (inst: int) -> bool:
    events.push("mutable:{inst}")
    st_mutable
st_error_host = (n: int):
    print(events)
    print("error:{n}:1")
    exit(19)
st_services = CheckerStatementHost(st_check_host, st_coerce_host, st_literal_host, st_resolve_host, st_clone_host, st_bind_host, st_truth_host, st_statement_host, st_block_host, st_mutable_host, st_error_host)
st_inputs = CheckerStatementInput(&nodes, &lists, &globals, &ctxs, &cx, &es_dropping, &st_refine_on, &es_last_at, &st_services)
st_bound = checker_statements_bind(&st_inputs)
show = (s: int):
    print("{s}:{int(nodes[s].kind)}:{nodes[s].list}:{nodes[s].nlist}:{nodes[s].aux}:{nodes[s].a}:{es_dropping}")
show_global = ():
    g = globals[globals.len() - 1]
    print("{g.name}:{g.type}:{g.decl}:{g.mod}:{g.is_const}:{g.state}:{g.init}")
const_of = (tn: int, value: int) -> int:
    s = node(.const_, tn); nodes[s].b = i32(value); nodes[s].name = 3; s
'''

MAIN = r'''
main = ():
    prepare()
    # Local constants: written types, literal defaults, inferred types; the module.
    s = const_of(node(.tname), typed(.int_lit, T_INT)); st_const(s); show(s); show_global()
    v = typed(.int_lit, T_INT); nodes[v].flags = i32(256)
    s = const_of(0, v); st_const(s); show(s); show_global()
    ctxs.push(FnCtx(inst = 1, mod = 7)); cx = 0
    st_grow = true
    s = const_of(0, typed(.ident, T_STR)); st_const(s); show(s); show_global()
    # `_ = value`: dropped on purpose, the flag restored.
    s = node(.assign, typed(.hole, 0)); nodes[s].b = i32(typed(.int_lit, T_INT)); st_drop(s); show(s)
    # `when`: the branch the condition picks, spliced in place; none.
    w = node(.when_, typed(.bool_lit, T_BOOL))
    nodes[w].b = i32(node(.block, 0, 0, 0, [stmt(typed(.ident, T_INT)), node(.return_)]))
    nodes[w].c = i32(node(.block, 0, 0, 0, [node(.break_)]))
    st_when(w); show(w)
    st_truth_value = true
    w = node(.when_, typed(.bool_lit, T_BOOL))
    nodes[w].b = i32(node(.block, 0, 0, 0, [stmt(typed(.ident, T_INT)), node(.return_)]))
    st_when(w); show(w)
    st_truth_value = false
    w = node(.when_, typed(.bool_lit, T_BOOL)); st_when(w); show(w)
    # `defer`: a block or a statement; refinement asks about mutable results.
    st_defer(node(.defer_, node(.block)))
    st_defer(node(.defer_, stmt(typed(.ident, T_INT))))
    st_refine_on = true
    st_defer(node(.defer_, node(.block)))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_statements_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN, extra_stems=STEMS).endswith(b'ok\n')


def test_checker_statements_errors(compiler, tmp_path):  # noqa: F811
    main = '''
main = ():
    prepare()
    ctxs.push(FnCtx(inst = 1)); cx = 0
    st_refine_on = true; st_mutable = true
    st_defer(node(.defer_, node(.block)))
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=STEMS)
    assert output.rstrip().endswith(b':1')
