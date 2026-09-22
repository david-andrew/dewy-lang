"""Public row inference grows possible behavior rather than assuming purity."""
from dewy.semantic import effect_inference as infer, effect_rows as rows

A, B = infer.PREFIX+'1', infer.PREFIX+'2'
PURE = rows.Contract(rows.Row())
ALLOC = rows.Contract(rows.Row((rows.Atom('allocates'),)))
FS = rows.Atom('reads', rows.Subject('resource', 'Filesystem'))


def variable(name):
    return rows.Contract(rows.Row(variables=(name,)))


def test_pure_recursion_has_an_empty_least_row():
    result = infer.solve({A: variable(B), B: variable(A)})
    assert result == {A: rows.Row(), B: rows.Row()}


def test_transitive_behavior_and_unknown_callbacks_propagate():
    assert infer.solve({A: variable(B), B: ALLOC})[A] == ALLOC.allowed
    assert infer.solve({A: variable(B), B: rows.Contract()})[A].unknown
    result = infer.solve({A: variable('E:parameter')})
    assert result[A] == rows.Row(variables=('E:parameter',))
    assert not infer.satisfied(infer.Constraint(variable(A), PURE), result)


def test_assignment_widens_an_inferred_callable_row():
    constraints = (infer.Constraint(variable(B), variable(A)),)
    result = infer.solve({A: PURE, B: ALLOC}, constraints)
    assert result[A] == ALLOC.allowed
    assert infer.satisfied(constraints[0], result)
    assert not infer.satisfied(infer.Constraint(variable(A), PURE), result)


def test_explicit_permission_is_removed_before_inferring_the_residual():
    actual = rows.Contract(rows.union(ALLOC.allowed, rows.Row((FS,))))
    required = rows.Contract(rows.Row((FS,), (A,)))
    result = infer.solve({A: PURE}, (infer.Constraint(actual, required),))
    assert result[A] == ALLOC.allowed
    assert infer.satisfied(infer.Constraint(actual, required), result)


def test_negative_contract_never_erases_a_possible_effect():
    forbidden = rows.Contract(excluded=(rows.Atom('allocates'),))
    result = infer.solve({A: ALLOC}, (infer.Constraint(variable(A), forbidden),))
    assert result[A] == ALLOC.allowed
    assert not infer.satisfied(infer.Constraint(variable(A), forbidden), result)
    assert not infer.satisfied(infer.Constraint(None, forbidden), result)


def test_missing_inference_definition_stays_unresolved():
    result = infer.solve({A: variable(B)})
    assert infer.pending(infer.resolve(variable(A), result))
    assert not infer.satisfied(infer.Constraint(variable(A), PURE), result)


def test_long_reverse_dependency_chain_reaches_the_same_row():
    names = [infer.PREFIX+str(index) for index in range(1000)]
    definitions = {name: variable(names[index+1]) for index, name in enumerate(names[:-1])}
    definitions[names[-1]] = ALLOC
    result = infer.solve(definitions)
    assert all(value == ALLOC.allowed for value in result.values())


def test_effect_solver_module_executes(tmp_path):
    from pathlib import Path
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile
    from tests.python_misc.test_scalar_projection import execute
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/effect_inference_solver.dewy'
    execute(tmp_path, 'effect-solver', codegen(SrcFile.from_path(fixture), debug_locations=False))


def test_native_effect_solver_module(tmp_path):
    from pathlib import Path
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    root = Path(__file__).resolve().parents[2]
    fixture = root / 'tests/fixtures/effect_inference_solver.dewy'
    source = fixture.read_text().replace('p"../../dewy/', f'p"{root}/dewy/')
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])


def test_public_inventory_infers_unannotated_bodies_and_call_edges():
    from dewy.reporting import SrcFile
    from dewy.semantic import check, hir
    from dewy.semantic.analyze import public_effects
    root = check.typecheck_and_resolve(SrcFile(None, '''
answer=():>int64=>42
forward=():>int64=>answer()
unknown=(f:():>int64):>int64=>f()
'''))
    functions = {node.name: node.expr for node in root.items if isinstance(node, hir.Declare)}
    summaries = public_effects.summarize(root, None)
    assert rows.implies(summaries[id(functions['answer'])], PURE)
    assert rows.implies(summaries[id(functions['forward'])], PURE)
    assert not rows.implies(summaries[id(functions['unknown'])], PURE)


def test_scoped_call_equations_translate_after_callback_inference():
    read = rows.Atom('reads', rows.Subject('parameter', '0'))
    projections = {
        'call:first': infer.Projection(variable(A), {'0': rows.Subject('parameter', '1', ('left',))}),
        'call:second': infer.Projection(variable(A), {'0': rows.Subject('parameter', '2', ('right',))}),
        'call:private': infer.Projection(variable(A), {'0': None}),
    }
    result = infer.solve_contracts({A: PURE, B: rows.Contract(rows.Row((read,)))},
                                  (infer.Constraint(variable(B), variable(A)),), projections)
    for name, slot, field in [('first', '1', 'left'), ('second', '2', 'right')]:
        expected = rows.Contract(rows.Row((rows.Atom('reads', rows.Subject('parameter', slot, (field,))),)))
        assert result['call:'+name] == expected
    assert result['call:private'] == PURE
    assert result[A].allowed.atoms == (read,)


def test_scoped_call_equations_preserve_unknown_and_do_not_strengthen_exclusions():
    source = rows.Atom('mutates', rows.Subject('parameter', '0', ('inner',)))
    target = rows.Atom('mutates', rows.Subject('parameter', '1', ('outer', 'inner')))
    no_target = rows.Contract(excluded=(target,))
    projection = {'call': infer.Projection(variable(A), {'0': rows.Subject('parameter', '1', ('outer',))})}
    constraints = (infer.Constraint(variable('call'), no_target),)
    result = infer.solve_contracts({A: rows.Contract(excluded=(source,))}, constraints, projection)
    assert infer.satisfied_contracts(constraints[0], result)
    assert not rows.implies(result['call'], PURE)
    result = infer.solve_contracts({A: rows.Contract()}, constraints, projection)
    assert not infer.satisfied_contracts(constraints[0], result)
    deep = {'call': infer.Projection(variable(A), {'0': rows.Subject('parameter', '1', ('nested',)*9)})}
    result = infer.solve_contracts({A: rows.Contract(excluded=(source,))}, constraints, deep)
    assert not result['call'].excluded  # truncating an exclusion would strengthen it


def test_recursive_scoped_call_equations_have_a_bounded_route_vocabulary():
    read = rows.Atom('reads', rows.Subject('parameter', '0', ('value',)))
    source = rows.Contract(rows.Row((read,), ('call',)))
    projections = {'call': infer.Projection(variable(A), {'0': rows.Subject('parameter', '0', ('child',))})}
    result = infer.solve_contracts({A: source}, projections=projections)
    assert result[A].allowed.atoms
    assert all(len(atom.subject.route) <= 8 for atom in result[A].allowed.atoms)
    assert any(atom.subject.route == ('child',)*8 for atom in result[A].allowed.atoms)
