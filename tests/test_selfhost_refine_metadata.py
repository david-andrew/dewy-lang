"""Read-only refinement metadata and storage routes agree with frozen Jo."""
import pytest

from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

LEAVES = ('refine_metadata',)
DRIVER = '''use 'main.jo'
use 'refine.jo'
use 'refinement_types.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'checker_types.dewy'
use 'checker_state.dewy'
use 'check.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'expr.jo'
use 'safe_paths.jo'
new_type = (info: TypeInfo) -> int:
    id = types.len(); types.push(info); id
plain_ids = (ids: int[]) -> int: ids[0]
main = ():
    init_types()
    # Stored predicates use canonical <= atoms; the resolver normalizes >=.
    ref_predicates = [[], [RefAtom(.le, RefTerm(1, -5), RefTerm()), RefAtom(.le, RefTerm(), RefTerm(1, 9))], [RefAtom(.le, RefTerm(), RefTerm(2))], [RefAtom(.le, RefTerm(), RefTerm(5))], [RefAtom(.le, RefTerm(), RefTerm(6))]]
    scalar = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=1))
    unsigned = new_type(TypeInfo(kind=.refined, elem=i32(T_U64), st=1))
    formal = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=2))
    sibling = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=3))
    stored = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), st=4))
    brand = new_type(TypeInfo(kind=.refined, elem=i32(T_STR), bits=-2))
    total = new_type(TypeInfo(kind=.refined, elem=i32(T_INT), bits=-1))
    inferred = new_type(TypeInfo(kind=.var, ref=i32(scalar)))
    assert(plain_ids([representation_type(inferred)]) == T_INT)
    assert(refine_read_type(brand) == brand and representation_type(brand) == T_STR)
    assert(refine_read_type(scalar) == T_INT and is_total_dict(total) and not is_total_dict(brand))
    assert(ref_has_formals(formal) and not ref_has_formals(sibling))
    assert(ref_has_fields(sibling) and not ref_has_fields(formal))
    assert(ref_self_stored(stored) and not ref_self_stored(scalar))
    b = ref_interval(scalar, FactBound(-100, 100))
    assert(b.lo == -5 and b.hi == 9)
    assert(ref_interval(unsigned, FactBound(-100, 100)) == FactBound(-100, 100))
    assert(ref_encoded(0, T_U64) == FACT_MIN and ref_encoded(-1, T_U64) == FACT_MAX)
    assert(ref_encoded(-1, T_INT) == -1)
    assert(ref_repr_match(T_INT, T_U64, [-1]) and not ref_repr_match(T_INT, T_U64, []))
    assert(ref_repr_match(T_INT, T_INT, []) and not ref_repr_match(T_INT, T_U64, [0]))
    si = structs.len(); structs.push(StructInfo(lit_set=7))
    set = new_type(TypeInfo(kind=.enum_, st=i32(si)))
    assert(str_set_of(set) == 7 and str_set_of(T_INT) == 0)
    record_fields = fields.len(); fields.push(Field(type=i32(sibling)))
    si = structs.len(); structs.push(StructInfo(fields=i32(record_fields), nfields=1))
    record = new_type(TypeInfo(kind=.struct_, st=i32(si)))
    assert(ref_dependent_record(record) and not ref_dependent_record(T_INT))
    array = mk_array(scalar); optional = mk_opt(scalar)
    nodes = fill(Node(), 32); locals = [Local(), Local(type=i32(array)), Local(flags=i32(LF_ALIAS), alias=1)]
    globals = [Global(), Global(type=i32(optional))]
    nodes[1] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(array))
    nodes[2] = Node(kind=.ident, aux=i32(int(SK.local)), sym=2, type=i32(array))
    nodes[3] = Node(kind=.index, a=2, type=i32(T_INT))
    assert(ref_place_alias(2) == 1 and refine_storage(2, 0) == array)
    assert(refine_storage(3, 0) == scalar and refine_storage(0, T_BOOL) == T_BOOL)
    ref_self_active = true; ref_self_elements[array] = sibling
    assert(refine_storage(3, 0) == sibling)
    ref_self_active = false
    nodes[4] = Node(kind=.ident, aux=i32(int(SK.global)), sym=1, type=i32(optional))
    nodes[5] = Node(kind=.unwrap, a=4, type=i32(T_INT))
    assert(refine_storage(5, 0) == scalar)
    nodes[6] = Node(kind=.ident, aux=i32(int(SK.local)), sym=1, type=i32(record))
    nodes[7] = Node(kind=.field, a=6, type=i32(T_INT))
    assert(refine_storage(7, 0) == sibling and ref_dependent_ancestor(7))
    locals[1].type = i32(brand); nodes[1].type = i32(brand)
    ut_safe_used = true
    assert(ref_safe_path_ancestor(3) and ref_dependent_ancestor(3))
    assert(not ref_safe_path_ancestor(1))
    loop i in [10..20): nodes[i] = Node(kind=.conv, a=i32(i+1))
    assert(ref_wrapped_check(10) == 18)
    nodes[12].aux = i32(int(CV.refinement))
    assert(ref_wrapped_check(10) == 12)
    nodes[21] = Node(kind=.call, aux=3); set_list(21, [12])
    assert(ref_wrapped_check(21) == 12)
    nodes[22] = Node(kind=.conv, aux=i32(int(CV.union_)), type=i32(optional))
    assert(refine_storage(22, 0) == optional)
    nodes[23] = Node(kind=.block); set_list(23, [12, 22])
    nodes[24] = Node(kind=.block, a=23)
    assert(not ref_pair_erased(24)); ref_pair_checks[24] = true
    assert(not ref_pair_erased(24)); nodes[12].ival = 1
    assert(ref_pair_erased(24))
    assert(not ref_self_direct_place(1)); ref_self_direct[1] = true
    assert(ref_self_direct_place(1) and not ref_self_direct_place(2))
    saved_types = types; saved_nodes = nodes; saved_predicates = ref_predicates
    loop i in [0..40):
        assert(refine_read_type(scalar) == T_INT and ref_has_fields(sibling))
        assert(refine_storage(5, 0) == scalar and ref_place_alias(2) == 1)
    assert(types == saved_types and nodes == saved_nodes and ref_predicates == saved_predicates)
    print("refinement metadata and storage routes ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_refine_metadata_state_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAVES)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAVES, jo_doubles=modules)


def test_refine_metadata_program_twins(compiler, tmp_path, monkeypatch):
    patterns = ('refinements/*.dewy', 'refine_union_storage/*.dewy',
                'self_length/*.dewy', 'sibling_length/*.dewy',
                'record_paired_fields/*.dewy', 'decided_path_contracts/*.dewy',
                'uint64_ceiling/*.dewy', 'literal_union_proof/*.dewy', 'literal_union_outcomes/*.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for pattern in patterns for p in (ROOT / 'tests/cases').glob(pattern)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAVES) > 50
