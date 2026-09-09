"""Compare HIR facts consumed by native bounds transfer with the hosted views."""

import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def identifier(name, type_, binding=None):
    return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding)


def integer(value):
    return hir.Integer(LOC, ty.IntegerLiteralType(value), '0d', value)


def test_native_hir_fact_views_match_hosted(tmp_path):
    x = identifier('i', 'int64', 1)
    xs = identifier('xs', ty.ArrayType('int64', None), 2)
    length = hir.ArrayLength(LOC, ty.addr_type(), xs)
    limits = [integer(2**63-1), integer(2**63), integer(-1), length]
    limits += [identifier('limit', t, 3) for t in ('int8', 'uint32', 'int64', 'uint64', 'int')]
    predicates = []
    for operator in ('__lt__', '__le__', '__gt__', '__ge__'):
        for limit in limits:
            operands = [x, limit] if operator in ('__lt__', '__le__') else [limit, x]
            predicates.append(hir.FunctionCall(LOC, 'bool', identifier(operator, ty.FunctionType([], [], None, 'bool')), operands, {}))
    predicates += [hir.ShortCircuit(LOC, 'bool', op, hir.Bool(LOC, 'bool', False), predicates[0]) for op in ('and', 'or')]
    positive = ty.Proposition('self', '>?', 0)
    small = ty.Proposition('self', '<?', 10)
    field_type = ty.ObjectType((ty.ObjectField('count', 'int64', refinement=(positive, small)),))
    second_type = ty.ObjectType((ty.ObjectField('count', 'int64', refinement=(positive,)),))
    ordinary = hir.MemberAccess(LOC, 'int64', identifier('a', field_type, 4), 'count')
    forwarded = hir.ForwardingAccess(LOC, 'int64', identifier('u', ty.union(field_type, second_type), 5), 'count', 'receiver', 6, ty.BOTTOM_TYPE)
    # Distinct shapes keep both alternatives, and only their common fact.
    second_type = ty.ObjectType((*second_type.fields, ty.ObjectField('other', 'bool')))
    forwarded.value.type = ty.union(field_type, second_type)
    exception = hir.ForwardingAccess(LOC, 'int64', forwarded.value, 'count', 'receiver', 6, 'error')
    nested_type = ty.ObjectType((ty.ObjectField('value', field_type, refinement=(ty.Proposition('.count', '=?', 4),)),))
    parent = hir.MemberAccess(LOC, field_type, identifier('nested', nested_type, 7), 'value')
    nested = hir.MemberAccess(LOC, 'int64', parent, 'count')
    accesses = [ordinary, forwarded, exception, nested]
    contract = ty.RefinedType('int64', (positive,))
    signature = ty.FunctionType([ty.PosOrKwArg('n', 'int64')], [], None, ty.optional(contract))
    overload = ty.OverloadType([ty.FunctionType([], [], None, 'bool'), signature])
    place = hir.Place(LOC, 'int64', x)
    call = hir.FunctionCall(LOC, ty.optional('int64'), identifier('f', overload, 8), [place], {}, selected_method_index=1)
    keyword = hir.FunctionCall(LOC, ty.optional('int64'), identifier('g', signature, 9), [], {'n': x})
    assignment = hir.IndexAssign(LOC, ty.VOID_TYPE, hir.Index(LOC, 'int64', xs, integer(0), 0), integer(1))
    root = hir.Block(LOC, ty.VOID_TYPE, [*predicates, *accesses, call, keyword, assignment], False)
    type_lines = []
    build = type_builder(type_lines)
    lines, root_id, names = emit_hir(root, type_value=build, with_names=True)
    checks, expected = [], []
    for i, predicate in enumerate(predicates):
        checks.append(f'    printl("guard{i}|{{analysis.predicate_bounds_counter({names[id(predicate)]} 1 nodes type_nodes)}}")')
        expected.append(f'guard{i}|{str(bounds.predicate_bounds_counter(predicate, 1)).lower()}')
    for i, access in enumerate(accesses):
        checks.append(f'    emit_props("field{i}" analysis.member_invariant({names[id(access)]} nodes type_nodes))')
        expected.extend(f'field{i}|{p.subject},{p.op},{p.value}' for p in bounds._member_invariant(access))
    for i, called in enumerate((call, keyword)):
        checks.append(f'    let argument{i} = analysis.call_argument({names[id(called)]} "n" nodes type_nodes)')
        checks.append(f'    printl("arg{i}|{{argument{i} =? {names[id(x)]}}}")')
        expected.append(f'arg{i}|true')
        checks.append(f'    loop refinement in analysis.call_result_refinements({names[id(called)]} nodes type_nodes) {{ emit_props("call{i}" refinement.propositions) }}')
        for refined in bounds._call_result_refinements(called):
            expected.extend(f'call{i}|{p.subject},{p.op},{p.value}' for p in refined.propositions)
    expected.extend(f'assigned|{binding}' for binding in bounds._assigned_binding_ids(root))
    source = tmp_path / 'hir_facts.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/hir_facts.dewy'}" as analysis
emit_props = (label:string props:array<facts.Proposition>):>void => {{
    loop p in props {{ printl("{{label}}|{{p.subject}},{{p.op}},{{_bigint_as_string(p.value)}}") }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
{chr(10).join(type_lines + lines + checks)}
    loop binding in analysis.assigned_binding_ids({root_id} nodes) {{ printl("assigned|{{binding}}") }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
