"""Public row rules: identity, negative guarantees and call substitution."""
import json
from pathlib import Path

import pytest

from dewy.semantic.effect_rows import Atom, Contract, Row, Subject, satisfies, subset, substitute, union, implies, identity
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_scalar_projection import execute

FS = Subject('resource', 'mint:17')
DB = Subject('resource', 'mint:18')
STATE = Subject('parameter', 'slot:0')
FIELD = Subject('parameter', 'slot:0', ('items',))
READ_FS = Atom('reads', FS)
WRITE_FS = Atom('mutates', FS)
READ_DB = Atom('reads', DB)

CASES = [
    (Row(), Contract(Row()), True),
    (Row(unknown=True), Contract(Row()), False),
    (Row(variables=('binder:1',)), Contract(Row()), False),
    (Row((READ_FS,)), Contract(Row((READ_FS, READ_DB))), True),
    (Row((READ_DB,)), Contract(Row((READ_FS,))), False),
    (Row((READ_FS,)), Contract(excluded=(Atom('reads'),)), False),
    (Row((WRITE_FS,)), Contract(excluded=(Atom('reads'),)), True),
    (Row((READ_DB,)), Contract(excluded=(READ_FS,)), True),
    (Row(unknown=True), Contract(excluded=(READ_FS,)), False),
    (Row(variables=('binder:1',)), Contract(excluded=(READ_FS,)), False),
    (Row(unknown=True), Contract(), True),
    (Row((READ_FS,)), Contract(Row((READ_FS,)), (READ_FS,)), False),
    (Row((Atom('reads', FIELD),)), Contract(Row((Atom('reads', STATE),))), True),
    (Row((Atom('reads', STATE),)), Contract(Row((Atom('reads', FIELD),))), False),
    (Row((Atom('reads', STATE),)), Contract(excluded=(Atom('reads', FIELD),)), False),
    (Row((READ_FS,)), Contract(Row((Atom('reads'),))), False),
]


@pytest.mark.parametrize('actual,contract,expected', CASES)
def test_contract_guarantees(actual, contract, expected):
    assert satisfies(actual, contract) is expected


def test_unknown_and_bound_row_variables_are_not_empty():
    variable = Row(variables=('binder:1',))
    assert subset(variable, variable)
    assert not subset(variable, Row(variables=('binder:2',)))
    assert not subset(Row(unknown=True), variable)
    assert subset(variable, Row(unknown=True))


def test_substitution_preserves_routes_and_caller_variable_identity():
    source = Row((Atom('mutates', FIELD), READ_FS), ('callee:E',))
    actual = Subject('parameter', 'caller:3', ('state',))
    result = substitute(source, {'callee:E': Row((READ_DB,), ('caller:E',))}, {'slot:0': actual})
    assert result == union(Row((Atom('mutates', Subject('parameter', 'caller:3', ('state', 'items'))), READ_FS, READ_DB), ('caller:E',)))
    assert substitute(Row(variables=('callee:E',)), {}) == Row(variables=('callee:E',))
    assert substitute(source, {'callee:E': Row()}, {'slot:0': None}) == Row((READ_FS,))


def test_row_union_is_order_independent_and_idempotent():
    root = Row((Atom('reads', STATE), READ_FS), ('binder:1',))
    child = Row((Atom('reads', FIELD), READ_DB), ('binder:1',))
    assert union(root, child) == union(child, root)
    assert union(root, root) == union(root)
    assert len(union(root, child).atoms) == 3


def test_native_rows_match_reviewed_contract_cases(tmp_path):
    def subject(value):
        if value is None:
            return 'none'
        route = ' '.join(json.dumps(field) for field in value.route)
        return f'rows.Subject[{json.dumps(value.kind)} {json.dumps(value.key)} [{route}]]'

    def atom(value):
        return f'rows.Atom[{json.dumps(value.family)} {subject(value.subject)}]'

    def row(value):
        if value is None:
            return 'none'
        atoms = ' '.join(atom(item) for item in value.atoms)
        variables = ' '.join(json.dumps(item) for item in value.variables)
        return f'rows.Row[[{atoms}] [{variables}] {str(value.unknown).lower()}]'

    assertions = []
    for actual, contract, expected in CASES:
        excluded = ' '.join(atom(item) for item in contract.excluded)
        assertions.append(f'$runtime_assert rows.satisfies({row(actual)} rows.Contract[{row(contract.allowed)} [{excluded}]]) =? {str(expected).lower()}')
    module = Path(__file__).resolve().parents[2] / 'dewy/bootstrap/semantic/effect_rows.dewy'
    source = SrcFile(tmp_path / 'effect-rows.dewy', f'''import p"{module}" as rows
main=():>int64=>{{
{chr(10).join(assertions)}
    let source=rows.Row[[rows.Atom['mutates' rows.Subject['parameter' 'slot:0' ['items']]]]]
    let supplied=rows.Subject['parameter' 'caller:3' ['state']]
    let mapped=rows.substitute(source [] ['slot:0' -> supplied])
    let expected=rows.Row[[rows.Atom['mutates' rows.Subject['parameter' 'caller:3' ['state' 'items']]]]]
    $runtime_assert rows.subset(mapped expected) and rows.subset(expected mapped)
    let private=rows.substitute(source [] ['slot:0' -> none])
    $runtime_assert rows.subset(private rows.Row[])
    let symbolic=rows.substitute(rows.Row[variables=['E']] [])
    $runtime_assert not rows.subset(symbolic rows.Row[])
    let root=rows.Row[[rows.Atom['reads' rows.Subject['parameter' 'slot:0']]]]
    let field=rows.Row[[rows.Atom['reads' rows.Subject['parameter' 'slot:0' ['items']]]]]
    $runtime_assert rows.merge(root field).atoms.length =? 1
    $runtime_assert rows.merge(field root).atoms.length =? 1
    let forward=rows.Contract[rows.merge(root field)]
    let reverse=rows.Contract[rows.merge(field root)]
    $runtime_assert rows.identity(forward) =? rows.identity(reverse)
    $runtime_assert rows.identity(none) not=? rows.identity(rows.Contract[rows.Row[]])
    $runtime_assert rows.implies(rows.Contract[rows.Row[]] none)
    $runtime_assert not rows.implies(none rows.Contract[rows.Row[]])
    return 42
}}''')
    source.path.write_text(source.body)
    execute(tmp_path, 'effect-rows', codegen(source))


def test_contract_subtyping_respects_open_negative_guarantees():
    no_reads = Contract(excluded=(Atom('reads'),))
    no_fs_reads = Contract(excluded=(READ_FS,))
    assert implies(no_reads, no_fs_reads)
    assert not implies(no_fs_reads, no_reads)
    assert not implies(None, no_reads)
    assert implies(Contract(Row()), no_reads)
    assert implies(Contract(Row((READ_DB,))), no_fs_reads)
    assert not implies(Contract(Row((READ_DB,))), no_reads)
    assert identity(None) != identity(Contract(Row()))
    assert identity(Contract(union(Row((READ_DB,)), Row((READ_FS,))))) == identity(Contract(union(Row((READ_FS,)), Row((READ_DB,)))))
