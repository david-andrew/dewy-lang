"""Substitute call contracts into native binding, length, and slice terms."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_fact_state import fact
from test_bootstrap_initialization import type_builder
from test_bootstrap_intervals import spelling
from test_bootstrap_relations import term

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_term_facts_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    def number(value):
        return hir.Integer(LOC, ty.IntegerLiteralType(value), '0d', value)

    def binary(name, left, right):
        function = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'int64'), name)
        return hir.FunctionCall(LOC, 'int64', function, [left, right], {})

    text = reference('text', ty.StringType(None))
    i = reference('i', 'int64')
    j = reference('j', 'int64')
    other = reference('other', ty.StringType(None))
    owner_type = ty.ObjectType((ty.ObjectField('text', ty.StringType(None)),))
    owner = reference('owner', owner_type)
    member = hir.MemberAccess(LOC, ty.StringType(None), owner, 'text')
    fixed = reference('fixed', ty.ArrayType('int64', 5))
    length = hir.StringLength(LOC, 'int64', text)
    end = binary('__sub__', length, number(1))
    refined_text = reference('refined_text', ty.RefinedType(ty.StringType(None),
                            (ty.Proposition('length', '>=?', 2),)))
    arguments = [text, other, member, fixed, i, length, refined_text]
    for left, right, delimiters in [
        (i, None, None), (i, j, '[)'), (i, j, '[]'),
        (i, length, '[)'), (i, end, '[]'), (None, j, '[)'),
        (None, j, '[]'), (i, j, '()'), (length, j, '[)'),
    ]:
        arguments.append(hir.StringSlice(LOC, ty.StringType(None), text, hir.Range(LOC, 'range', delimiters, None, left, right)))
    calls = []
    functions = {}
    for subject in ['self', 'length']:
        for projection in ['value', 'length']:
            for op in ['<?', '<=?', '>?', '>=?', '=?', 'not=?']:
                # Multiple result alternatives each contribute their own
                # contracts, as in the hosted helper. Selection of a result
                # alternative during flow narrowing happens in the caller.
                for argument in arguments:
                    refined = ty.RefinedType('int64' if subject == 'self' else ty.StringType(None),
                                             (ty.Proposition(subject, op, 0, term='src', term_of=projection),))
                    signature = ty.FunctionType([ty.PosOrKwArg('src', argument.type, True)], [], None, refined)
                    function = functions.setdefault(repr(signature), hir.ExpressedIdentifier(LOC, signature, 'measure'))
                    calls.append((subject, hir.FunctionCall(LOC, refined, function, [argument], {})))
    # Keyword calls and selected overloads use the selected parameter names.
    selected = ty.FunctionType([ty.PosOrKwArg('src', text.type, True)], [], None,
                              ty.RefinedType('int64', (ty.Proposition('self', '=?', 0, term='src'),)))
    irrelevant = ty.FunctionType([], [], None, 'int64')
    overload = hir.ExpressedIdentifier(LOC, ty.OverloadType((irrelevant, selected)), 'overload')
    calls.append(('self', hir.FunctionCall(LOC, selected.ret, overload, [], {'src': text}, selected_method_index=1)))
    expressions = [i, length, end, binary('__sub__', end, number(1)),
                   binary('__add__', number(3), i), binary('__sub__', i, number(-2)),
                   binary('__mul__', i, number(2)), binary('__sub__', length, number(0)),
                   binary('__sub__', hir.StringLength(LOC, 'int64', other), number(1))]
    root = hir.Block(LOC, ty.VOID_TYPE, [*(node for _, node in calls), *expressions], False)
    base_bindings = list(registry.by_id.values())
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in base_bindings]
    checks, expected = [], []
    for index, (subject, node) in enumerate(calls):
        promises = validator._call_facts(node, subject)
        expected.extend(f'call{index}|{term(upper)}|{offset}|{gap}|{direction}' for upper, offset, gap, direction in promises)
    for index, node in enumerate(expressions):
        offset = validator._offset_term(node)
        length_offset = validator._length_offset_index(node, text.binding_id)
        checks.append(f'    emit_offset("offset{index}" terms.offset_term({names[id(node)]} env @registry))')
        expected.append(f'offset{index}|none' if offset is None else f'offset{index}|{term(offset[0])}|{offset[1]}')
        checks.append(f'    printl("length{index}|{{endpoint(terms.length_offset({names[id(node)]} {text.binding_id} env @registry))}}")')
        expected.append(f'length{index}|{length_offset}')
    # The symbolic result facts are independent of concrete interval seeding.
    # Check both scalar and length subjects, and do not infer nonnegativity
    # of a slice start from its spelling alone.
    for index, (subject, node) in enumerate(calls):
        for lower in [-1, 0]:
            state = {i.binding_id: bounds.Interval(lower, 7)}
            validator._seed_call_term_facts(100, node, state)
            relational = {key: value for key, value in state.items()
                          if bounds._decode_order_fact(key) is not None or bounds._decode_remainder_fact(key) is not None}
            expected.extend(f'seed{index}_{lower+1}|{fact(key)[1]}|{spelling(value)}' for key, value in relational.items())
    cases = ' '.join(f'Case[{names[id(node)]} {json.dumps(subject)}]' for subject, node in calls)
    source = tmp_path / 'term_facts.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/value_bounds.dewy'}" as values
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/term_facts.dewy'}" as terms
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/fact_state.dewy'}" as flow
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/relations.dewy'}" as relations
Case:type = const [node:addr subject:string]
term_text = (value:flow.Term):>string => if value.projection =? 'length' "facts.Term[{{value.binding_id}} 'length']" else "facts.Term[{{value.binding_id}}]"
endpoint = (value:bigint?):>string => if value is? none 'None' else _bigint_as_string(value)
emit = (label:string promises:array<terms.CallFact>):>void => {{
    loop p in promises {{
        let offset = if p.offset is? none 'None' else "{{p.offset}}"
        printl("{{label}}|{{term_text(p.upper)}}|{{offset}}|{{_bigint_as_string(p.gap)}}|{{p.direction}}")
    }}
}}
emit_offset = (label:string offset:terms.Offset?):>void => {{
    if offset is? none {{ printl("{{label}}|none") }}
    else {{ printl("{{label}}|{{term_text(offset.term)}}|{{_bigint_as_string(offset.shift)}}") }}
}}
emit_state = (label:string state:flow.State):>void => {{
    loop entry in state.values {{
        if entry.fact is? flow.Order | flow.Remainder {{
            let lo = if entry.interval.lower is? none '-' else _bigint_as_string(entry.interval.lower)
            let hi = if entry.interval.upper is? none '+' else _bigint_as_string(entry.interval.upper)
            printl("{{label}}|{{entry.fact.key}}|{{lo}},{{hi}},{{entry.interval.capped}}")
        }}
    }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry {validator.max_length}]
    let context = relations.Context[flow.Context[cap={validator.max_length}]]
    let cases:array<Case> = [{cases}]
    loop index in 0.. and index <? cases.length {{
        let test = cases[index]
        let promises = terms.call_facts(test.node test.subject env @registry)
        emit("call{{index}}" promises)
        loop pass in 0..1 {{
            let state:flow.State = []
            let lower:bigint = if pass =? 0 (-1) else 0
            flow.put(@state flow.value(flow.Term[{i.binding_id}]) ranges.Interval[lower 7])
            let projection:facts.Projection = if test.subject =? 'self' 'value' else 'length'
            terms.seed(@state flow.Term[100 projection] promises context)
            emit_state("seed{{index}}_{{pass}}" state)
        }}
    }}
{chr(10).join(checks)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(expected)
