from dewy.semantic import effect_inference as infer, effect_rows as rows

A, B = infer.PREFIX+'a', infer.PREFIX+'b'
FS = rows.Atom('reads', rows.Subject('resource', 'Filesystem'))
NO_FS = rows.Contract(excluded=(FS,))
PURE = rows.Contract(rows.Row())


def variable(name):
    return rows.Contract(rows.Row(variables=(name,)))


def test_inferred_forwarding_keeps_an_open_negative_guarantee():
    solutions = infer.solve_contracts({A: variable(B), B: NO_FS})
    assert solutions[A].allowed.unknown
    assert infer.satisfied_contracts(infer.Constraint(variable(A), NO_FS), solutions)
    assert not infer.satisfied_contracts(infer.Constraint(variable(A), PURE), solutions)


def test_unknown_assignment_invalidates_an_inferred_guarantee():
    constraints = (infer.Constraint(None, variable(A)),)
    solutions = infer.solve_contracts({A: NO_FS}, constraints)
    assert not solutions[A].excluded
    assert not infer.satisfied_contracts(infer.Constraint(variable(A), NO_FS), solutions)


def test_required_exclusion_is_only_a_candidate_not_a_proof():
    edge = infer.Constraint(variable(A), NO_FS)
    solutions = infer.solve_contracts({A: rows.Contract()}, (edge,))
    assert not infer.satisfied_contracts(edge, solutions)


def test_recursive_unknown_operation_cannot_prove_its_own_absence():
    edge = infer.Constraint(variable(A), NO_FS)
    solutions = infer.solve_contracts({A: variable(B), B: rows.join(variable(A), rows.Contract())}, (edge,))
    assert not solutions[A].excluded
    assert not solutions[B].excluded


def test_written_permissions_are_removed_before_checking_the_residual():
    edge = infer.Constraint(rows.Contract(rows.Row((FS,))), rows.Contract(rows.Row((FS,), (A,)), ()))
    solutions = infer.solve_contracts({A: PURE}, (edge, infer.Constraint(variable(A), NO_FS)))
    assert infer.satisfied_contracts(infer.Constraint(variable(A), NO_FS), solutions)


def test_guarantees_flow_without_adding_permissions():
    allocation = rows.Atom('allocates')
    solutions = infer.solve_contracts({A: rows.join(variable(B), rows.Contract(rows.Row((allocation,)))), B: NO_FS})
    assert solutions[A].allowed.unknown
    assert allocation in solutions[A].allowed.atoms
    assert infer.satisfied_contracts(infer.Constraint(variable(A), NO_FS), solutions)


def test_inferred_negative_wrapper_executes(tmp_path):
    from pathlib import Path
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile
    from tests.python_misc.test_scalar_projection import execute
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/inferred_effect_guarantees.dewy'
    execute(tmp_path, 'effect-guarantees', codegen(SrcFile.from_path(fixture)))


def test_unknown_callback_does_not_inherit_a_requested_guarantee():
    import pytest
    from pathlib import Path
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile, ReportException
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/inferred_effect_guarantees_rejected.dewy'
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile.from_path(fixture))


def test_native_inferred_effect_guarantees(tmp_path):
    from pathlib import Path
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    root = Path(__file__).resolve().parents[2]
    fixtures = root / 'tests/fixtures'
    kernel = (fixtures / 'effect_inference_solver.dewy').read_text().replace('../../dewy/', str(root / 'dewy') + '/')
    check_structural_text(build_program_driver(tmp_path), tmp_path,
                          cases=[kernel, (fixtures / 'inferred_effect_guarantees.dewy').read_text()],
                          errors=[(fixtures / 'inferred_effect_guarantees_rejected.dewy').read_text()])
