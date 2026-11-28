"""The obligation classifier preserves narrowing and early-return decisions."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_facts_obligations import DRIVER as WALK_DRIVER

pytestmark = pytest.mark.nightly

LEAF = ('facts_lifecycle',)
CLASSIFIER = '''    init_types()
    nodes[20] = Node(kind=.int_lit, type=i32(T_INT), ival=0)
    nodes[21] = Node(kind=.int_lit, type=i32(T_INT), ival=3)
    nodes[22] = Node(kind=.binary, type=i32(T_INT), a=21, b=20, op_ext=node_with_op(u32(0), i32(i32(int(Tok.slash)))))
    if not fact_obligation_node(22): exit(40)
    nodes[22].b = 21
    if fact_obligation_node(22): exit(41)
    nodes[22].b = 20
    nodes[22].op_ext = node_with_op(nodes[22].op_ext, i32(i32(int(Tok.percent))))
    if not fact_obligation_node(22): exit(42)
    nodes[22].aux = 1
    if fact_obligation_node(22): exit(43)
    nodes[23] = Node(kind=.int_lit, type=i32(T_MATH_INT), ival=2)
    nodes[24] = Node(kind=.conv, type=i32(T_INT), a=23, aux=i32(int(CV.int_)))
    if not fact_obligation_node(24): exit(44)
    nodes[24].type = i32(T_MATH_INT)
    if fact_obligation_node(24): exit(45)
    nodes[24].aux = i32(int(CV.refinement))
    if not fact_obligation_node(24): exit(46)
    nodes[24].aux = i32(int(CV.arr2fixed))
    if not fact_obligation_node(24): exit(47)
    nodes[25] = Node(kind=.binary, type=i32(T_MATH_INT), a=23, b=20, op_ext=node_with_op(u32(0), i32(i32(int(Tok.shl)))))
    if not fact_obligation_node(25): exit(48)
    nodes[25].a = 21
    if fact_obligation_node(25): exit(49)
    nodes[26] = Node(kind=.ident, type=i32(mk_array(T_INT)))
    nodes[27] = Node(kind=.index, type=i32(T_INT), a=26, b=20)
    if not fact_obligation_node(27): exit(50)
    nodes[27].flags = i32(NF_INBOUNDS)
    if fact_obligation_node(27): exit(51)
    nodes[27].flags = 0
    nodes[26].type = i32(T_STR)
    if fact_obligation_node(27): exit(52)
'''
DRIVER = WALK_DRIVER.replace("use 'expr.jo'", "use 'expr.jo'\nuse 'types.jo'\nuse 'type_ops.dewy'\nuse 'checker_tokens.dewy'").replace('    print("obligation discovery ok")', CLASSIFIER + '    print("obligation classifier ok")')


@pytest.mark.parametrize('release', [False, True])
def test_facts_obligation_node_twins(compiler, tmp_path, release):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)
