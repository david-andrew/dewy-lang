"""An inferred record field's contract: which values bring their declared refinement, and which stay plain."""
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

LEAF = ('record_field_contracts',)

DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'refinement_types.dewy'
use 'refine.jo'
use 'types.jo'
main = ():
    nodes = fill(Node(), 64)
    locals = fill(Local(), 8)
    fns = fill(FnInst(), 4)
    types = fill(TypeInfo(), 10)
    refine_active = true
    # 1 int64, 2 Count (1 to 400), 3 a contract naming a parameter, 4 Count?, 5 Count | Oops, 7 Small (1 to 9)
    types[1] = TypeInfo(kind = .int_, bits = 64, sign = true)
    types[2] = TypeInfo(kind = .refined, elem = 1, st = 1)
    types[3] = TypeInfo(kind = .refined, elem = 1, st = 2)
    types[4] = TypeInfo(kind = .opt, elem = 2)
    types[6] = TypeInfo(kind = .struct_)
    types[7] = TypeInfo(kind = .refined, elem = 1, st = 3)
    self = RefTerm(kind = 0)
    ref_predicates = [[], [RefAtom(.le, RefTerm(kind = 1, value = 1), self), RefAtom(.le, self, RefTerm(kind = 1, value = 400))],
        [RefAtom(.le, RefTerm(kind = 2, value = 0), self)],
        [RefAtom(.le, RefTerm(kind = 1, value = 1), self), RefAtom(.le, self, RefTerm(kind = 1, value = 9))]]
    structs = fill(StructInfo(), 2)
    structs[1] = StructInfo(union_ = true, targs = 0, ntargs = 2)
    type_args = [2, 6]
    types[5] = TypeInfo(kind = .enum_, st = 1)
    # a parameter declared Count, one with a dependent contract, one Count?, one Small
    locals[1] = Local(type = 2)
    locals[2] = Local(type = 3)
    locals[3] = Local(type = 4)
    locals[5] = Local(type = 7)
    nodes[1] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 1, type = 1)
    nodes[2] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 2, type = 1)
    nodes[3] = Node(kind = .int_lit, ival = 5, type = 1)
    nodes[4] = Node(kind = .int_lit, ival = 0, type = 1)
    nodes[5] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 3, type = 1)
    nodes[25] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 5, type = 1)
    print("param {field_contract(1, 1)} dependent {field_contract(2, 1)} literal {field_contract(3, 1)}")
    print("other representation {field_contract(1, 4)}")
    # direct calls: a declared result, and `or_throw`'s member of a declared union
    fns[1] = FnInst(ret = 2)
    fns[2] = FnInst(ret = 5)
    nodes[6] = Node(kind = .call, aux = 0, sym = 1, type = 1)
    nodes[7] = Node(kind = .call, aux = 0, sym = 2, type = 1)
    nodes[8] = Node(kind = .call, aux = 1, sym = 1, type = 1)
    print("result {field_contract(6, 1)} union member {field_contract(7, 1)} indirect {field_contract(8, 1)}")
    # arms: a literal inside the contract, one outside it, a narrower contract, one that leaves
    nodes[9] = Node(kind = .if_, a = 3, b = 1, c = 3, type = 1)
    nodes[10] = Node(kind = .if_, a = 3, b = 1, c = 4, type = 1)
    nodes[11] = Node(kind = .if_, a = 3, b = 3, c = 1, type = 1)
    nodes[12] = Node(kind = .continue_, type = i32(T_NEVER))
    nodes[13] = Node(kind = .if_, a = 3, b = 4, c = 12, type = 1)
    nodes[14] = Node(kind = .conv, a = 12, type = 1)
    nodes[15] = Node(kind = .if_, a = 3, b = 14, c = 1, type = 1)
    nodes[26] = Node(kind = .if_, a = 3, b = 1, c = 25, type = 1)
    print("arms {field_contract(9, 1)} {field_contract(10, 1)} {field_contract(11, 1)} {field_contract(13, 1)} {field_contract(15, 1)} {field_contract(26, 1)}")
    # `??`: a fallback inside the payload's contract, one outside, one that leaves
    nodes[16] = Node(kind = .coalesce, a = 5, b = 3, type = 1)
    nodes[17] = Node(kind = .coalesce, a = 5, b = 4, type = 1)
    nodes[18] = Node(kind = .coalesce, a = 5, b = 14, type = 1)
    print("coalesce {field_contract(16, 1)} {field_contract(17, 1)} {field_contract(18, 1)}")
    # `f(x) or_throw` checked: {let tmp = f(x); if tmp is? E return tmp; tmp}, tmp read through
    # its narrowed alias; any other statement in between keeps the field plain
    locals[4] = Local(type = 5)
    locals[6] = Local(type = 1, flags = i32(LF_ALIAS), alias = 22)
    nodes[19] = Node(kind = .vardecl, sym = 4, b = 7)
    nodes[20] = Node(kind = .return_)
    nodes[21] = Node(kind = .if_, a = 3, b = 20)
    nodes[22] = Node(kind = .narrow, a = 23)
    nodes[23] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 4)
    nodes[24] = Node(kind = .ident, aux = i32(int(SK.local)), sym = 6, type = 1)
    nodes[27] = Node(kind = .exprstmt, a = 24)
    nodes[28] = Node(kind = .assign, a = 23, b = 4)
    lists = [19, 21, 27, 19, 28, 27]
    nodes[30] = Node(kind = .block, list = 0, nlist = 3, type = 1)
    nodes[31] = Node(kind = .block, list = 3, nlist = 3, type = 1)
    print("or_throw {field_contract(30, 1)} with a write {field_contract(31, 1)}")
    refine_active = false
    print("inactive {field_contract(1, 1)}")
    print("record field contracts ok")
'''


def test_record_field_contracts_leaf(compiler, tmp_path):  # noqa: F811
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    out = compare_leaf(compiler, tmp_path, False, DRIVER, extra_stems=LEAF, jo_doubles=modules)
    assert out.endswith(b'record field contracts ok\n')
