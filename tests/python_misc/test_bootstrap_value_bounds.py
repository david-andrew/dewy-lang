"""Native evidence from constants, storage contracts, and iterator sources."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_value_bounds_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()
    declarations = []

    def number(n, type_=None):
        return hir.Integer(LOC, ty.IntegerLiteralType(n) if type_ is None else type_, '0d', n)

    def declare(name, type_, expr, const=False, store_type=None):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = expr.type
        binding.store_type = store_type
        node = hir.Declare(LOC, ty.VOID_TYPE, 'const' if const else 'let', name, type_, expr, binding_id=binding.id)
        binding.declaration = node
        declarations.append(node)
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    scalar_types = ['int8', 'uint8', 'uint64', 'int', ty.addr_type(), ty.nat_type('nat32'),
                    ty.optional('int16'), ty.union('int8', 'int64', 'none'), ty.optional(ty.addr_type())]
    references = [declare(f'v{i}', type_, number(0)) for i, type_ in enumerate(scalar_types)]
    references.append(declare('place', 'int64', number(1), store_type=ty.RefinedType('int64', (ty.Proposition('self', '>=?', 3),))))
    saved = declare('saved', 'int64', number(7), const=True)
    alias = declare('alias', 'int64', saved, const=True)
    constants = [*references, saved, alias, number(-(10**80)), number(10**80)]
    # Materialized numeric representations carry meaning independently of
    # the library helper's symbol or the object's field spelling.
    big = hir.ObjectLiteral(LOC, ty.ObjectType(()), [], integer_value=10**80)
    helper = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'int'), 'library_helper')
    constants.extend([
        big,
        hir.FunctionCall(LOC, 'int', helper, [big, number(1)], {}, integer_operation='__add__'),
        hir.FunctionCall(LOC, 'int', helper, [number(17)], {}, integer_operation='identity'),
        hir.FunctionCall(LOC, 'uint8', helper, [number(255)], {}, integer_operation='narrow'),
        hir.FunctionCall(LOC, 'uint8', helper, [number(256)], {}, integer_operation='narrow'),
        hir.FunctionCall(LOC, 'int', helper, [number(-10), number(3)], {}, integer_operation='__floordiv__'),
        hir.FunctionCall(LOC, 'int', helper, [number(10), number(-3)], {}, integer_operation='__floordiv__'),
        hir.FunctionCall(LOC, 'int', helper, [number(10), number(-3)], {}, integer_operation='__mod__'),
        hir.FunctionCall(LOC, 'int64', hir.ExpressedIdentifier(LOC, helper.type, 'identity'), [number(17)], {}),
        hir.FunctionCall(LOC, 'int64', hir.ExpressedIdentifier(LOC, helper.type, 'narrow'), [number(17)], {}),
    ])
    binary_type = ty.FunctionType([], [], None, 'int64')
    for name, a, b, result_type in [('__add__', 1, 2, 'int64'), ('__sub__', 0, 3, 'int64'),
                                    ('__mul__', 100, 100, 'int8'), ('__mul__', 10**40, 10**40, 'int'),
                                    ('__floordiv__', -10, 3, 'int64'), ('__eq__', 1, 1, 'bool')]:
        function = hir.ExpressedIdentifier(LOC, binary_type, name)
        constants.append(hir.FunctionCall(LOC, result_type, function, [number(a), number(b)], {}))
    array_type = ty.ArrayType('int64', 3)
    array = hir.ArrayLiteral(LOC, array_type, [number(-3), alias, number(20)])
    sequence = declare('sequence', array_type, array)
    length = hir.ArrayLength(LOC, 'int64', sequence)
    constants.append(length)
    iterators = [
        hir.IteratorExpression(LOC, 'bool', references[0], sequence, 0, 1, 2, 3),
        hir.IteratorExpression(LOC, 'bool', references[0], hir.Void(LOC, 'range'), 3, 2, 9, 4),
        hir.IteratorExpression(LOC, 'bool', references[0], hir.Void(LOC, 'range'), 9, -2, 3, 4),
        hir.IteratorExpression(LOC, 'bool', references[0], hir.Void(LOC, 'range'), 0, 1, None, None),
        hir.IteratorExpression(LOC, 'bool', references[0], hir.Void(LOC, 'range'), 0, 1, None, None, guarded=True),
        hir.IteratorExpression(LOC, 'bool', hir.ExpressedIdentifier(LOC, ty.optional('int8'), 'optional'), sequence, 0, 1, 2, 3),
        hir.IteratorExpression(LOC, 'bool', hir.ExpressedIdentifier(LOC, ty.union('int8', 'int64'), 'mixed'), sequence, 0, 1, 2, 3),
        hir.IteratorExpression(LOC, 'bool', references[0], hir.Void(LOC, 'range'), 0, -1, None, None),
    ]
    root = hir.Block(LOC, ty.VOID_TYPE, [*declarations, *constants, *iterators], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator._record_element_intervals(sequence.binding_id, array)
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = []
    for binding in registry.by_id.values():
        registry_lines.append(f'''    registry.by_id[{binding.id}] = bindings.Binding[
        id={binding.id} name={json.dumps(binding.name)} kind="value" loc=span
        value_type={build(binding.type)} declaration={names[id(binding.declaration)]}
        store_type={"none" if binding.store_type is None else build(binding.store_type)}
    ]''')
    checks, expected = [], []

    def emit(label, expression, value):
        checks.append(f'    emit("{label}" {expression})')
        expected.append(f'{label}|none' if value is None else f'{label}|{value.lower},{value.upper},{str(value.capped).lower()}')

    for i, node in enumerate(constants):
        emit(f'constant{i}', f'values.constant({names[id(node)]} env)', validator._constant_expr(node, set()))
    for binding in registry.by_id.values():
        emit(f'type{binding.id}', f'values.type_interval({binding.id} env)', validator._type_interval(binding.id))
    emit('elements', f'values.literal_elements({names[id(array)]} env)', validator._literal_element_interval(array))
    for i, iterator in enumerate(iterators):
        checks.append(f'    let iterator{i} = hir.node_at(nodes {names[id(iterator)]})')
        checks.append(f'    $runtime_assert iterator{i} is? hir.IteratorExpression')
        emit(f'iterator{i}', f'values.loop_counter_interval(iterator{i} elements env)', validator._loop_counter_interval(iterator))
    source = tmp_path / 'value_bounds.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/value_bounds.dewy'}" as values
endpoint = (value:bigint?):>string => if value is? none 'None' else _bigint_as_string(value)
emit = (label:string value:ranges.Interval?):>void => {{
    if value is? none {{ printl("{{label}}|none") }}
    else {{ printl("{{label}}|{{endpoint(value.lower)}},{{endpoint(value.upper)}},{{value.capped}}") }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry {validator.max_length}]
    let elements:values.ElementIntervals = []
    values.record_elements(@elements {sequence.binding_id} {names[id(array)]} env)
{chr(10).join(checks)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
