"""Native index diagnostics and lowering hints agree with hosted validation."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_fact_state import fact
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 1)


def test_native_index_checks_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()
    srcfile = SrcFile(None, 'i')

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    i = reference('i', 'int64')
    array = reference('array', ty.ArrayType('int64', None))
    text = reference('text', ty.StringType(None))
    fixed = reference('fixed', ty.ArrayType('int64', 5))
    empty = reference('empty', ty.ArrayType('int64', 0))
    literal = hir.String(LOC, ty.StringLiteralType('a\u0301b'), 'a\u0301b')
    indices = [hir.Integer(LOC, ty.IntegerLiteralType(value), '0d', value) for value in [-1, 0, 1, 4, 5]] + [i]
    queries = []
    for sequence in [array, text, fixed, empty, literal]:
        length = hir.ArrayLength(LOC, 'int64', sequence) if isinstance(sequence.type, ty.ArrayType) else hir.StringLength(LOC, 'int64', sequence)
        fn = hir.ExpressedIdentifier(LOC, ty.FunctionType([], [], None, 'int64'), '__sub__')
        end = hir.FunctionCall(LOC, 'int64', fn, [length, indices[2]], {})
        for index in [*indices, end, length]:
            constructor = hir.Index if isinstance(sequence.type, ty.ArrayType) else hir.StringIndex
            queries.append(constructor(LOC, 'int64', sequence, index, None))
    root = hir.Block(LOC, 'void', queries, False)
    validator = bounds._BoundsValidator(registry, srcfile, root)
    validator.max_length = 1024
    interval, key = bounds.Interval, bounds._length_key
    states = [
        {},
        {i.binding_id: interval(0, 4), key(array.binding_id): interval(5, 8), key(text.binding_id): interval(5, 8)},
        {i.binding_id: interval(0, None), bounds._index_fact_key(i.binding_id, array.binding_id): interval(None, None)},
        {i.binding_id: interval(-1, 4), bounds._index_fact_key(i.binding_id, array.binding_id): interval(None, None)},
    ]
    type_lines = []
    build = type_builder(type_lines)
    lines, _, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = [f'    registry.by_id[{b.id}] = bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]'
                      for b in registry.by_id.values()]

    def native_interval(value):
        if value is None:
            return 'none'
        lo = 'none' if value.lower is None else f'({value.lower})'
        hi = 'none' if value.upper is None else f'({value.upper})'
        return f'ranges.Interval[{lo} {hi} {str(value.capped).lower()}]'

    def diagnostic(error):
        report = error.report
        return f'error|{report.title}|{report.pointer_messages[0].message}|{report.hint}|{";".join(report.notes)}'

    expected, checks = [], []
    for state_index, state in enumerate(states):
        entries = [f'    flow.put(@state {fact(k)[0].replace("facts.", "flow.")} {native_interval(v)})' for k, v in state.items()]
        cases, evaluated = [], {}
        for index, query in enumerate(queries):
            sequence = query.array if isinstance(query, hir.Index) else query.string
            index_interval = validator._eval(query.index, dict(state), validate=False)
            length_interval = validator._length_interval(sequence, dict(state))
            evaluated[names[id(query.index)]] = index_interval
            query.constant_index = None
            try:
                validator._validate_index(query, index_interval, dict(state))
                result = f'ok|{query.constant_index}'
            except UserError as error:
                result = diagnostic(error)
            expected.append(f'{state_index}|{index}|{result}')
            cases.append(f'Case[{names[id(query)]} {native_interval(index_interval)} {native_interval(length_interval)}]')
            if sequence is array:
                for allow_end, method in [(False, 'pop'), (True, 'insert')]:
                    function = hir.ArrayMethod(LOC, ty.FunctionType([], [], None, 'int64'), array, method)
                    call = hir.FunctionCall(LOC, 'int64', function, [query.index], {})
                    try:
                        validator._validate_method_index(call, query.index, index_interval, dict(state), array.binding_id,
                                                         length_interval or validator._length_default(), allow_end=allow_end)
                        result = 'ok'
                    except UserError as error:
                        result = diagnostic(error)
                    expected.append(f'{state_index}|{index}|{method}|{result}')
        snapshot = ' '.join(f'{node} -> {native_interval(value)}' for node, value in evaluated.items() if value is not None)
        checks.append(f'''    state.clear
{chr(10).join(entries)}
    let context{state_index} = proofs.Context[env relation_context]
    let observed{state_index}:dict<addr ranges.Interval>=[{snapshot}]
    emit_cases({state_index} [{' '.join(cases)}] {array.binding_id} state context{state_index} observed{state_index} srcfile @registry)''')
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('facts', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('proofs', 'analyze/length_proofs.dewy'),
        ('checks', 'analyze/index_checks.dewy'), ('flow', 'analyze/fact_state.dewy'),
        ('ranges', 'analyze/intervals.dewy'), ('relations', 'analyze/relations.dewy'),
    ])
    source = tmp_path / 'index_checks.dewy'
    source.write_text(f'''from reporting import Span, SrcFile, Error
{imports}
Case:type = const [node:addr interval:ranges.Interval? length:ranges.Interval?]
emit_error = (label:string error:Error):>void => {{
    $runtime_assert error.pointers.length >? 0
    let hint = if error.hint is? none 'None' else error.hint
    printl("{{label}}|error|{{error.title}}|{{error.pointers[0].message}}|{{hint}}|{{error.notes.join';'}}")
}}
emit_cases = (label:addr cases:array<Case> array:addr state:flow.State context:proofs.Context observed:dict<addr ranges.Interval> srcfile:SrcFile @registry:bindings.Registry):>void => {{
    loop index in 0.. and index <? cases.length {{
        let test = cases[index]
        let node = hir.node_at(context.env.nodes test.node)
        $runtime_assert node is? hir.Index|hir.StringIndex
        let result = checks.check_index(node test.interval test.length state context observed srcfile @registry)
        if result is? Error {{ emit_error("{{label}}|{{index}}" result) }}
        else {{
            let constant = if result.constant_index is? none 'None' else _bigint_as_string(result.constant_index)
            printl("{{label}}|{{index}}|ok|{{constant}}")
        }}
        if node is? hir.Index {{
            let receiver = hir.node_at(context.env.nodes node.array)
            if receiver is? hir.ExpressedIdentifier and receiver.binding_id =? array {{
                loop allow_end in [false true] {{
                    let method = if allow_end 'insert' else 'pop'
                    let length = if test.length is? none values.length_default(1024) else test.length
                    let problem = checks.check_method_index(method node.index test.interval state array length allow_end context observed srcfile @registry)
                    if problem is? none {{ printl("{{label}}|{{index}}|{{method}}|ok") }}
                    else {{ emit_error("{{label}}|{{index}}|{{method}}" problem) }}
                }}
            }}
        }}
    }}
}}
main = ():>int64 => {{
    let span = Span[0 1]
    let srcfile = SrcFile['fixture' 'i']
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let env = values.Environment[nodes type_nodes registry 1024]
    let relation_context = relations.Context[flow.Context[cap=1024 widths=[
        {i.binding_id} -> ranges.Interval[(-9223372036854775808) 9223372036854775807]
    ]]]
    let state:flow.State = []
{chr(10).join(checks)}
    # A saved index is not the binding's current value after another
    # argument has assigned it. Current symbolic facts cannot prove that
    # earlier observation, even though its nonnegative interval survives.
    state.clear
    flow.put(@state flow.index({i.binding_id} {array.binding_id}) ranges.UNKNOWN)
    let observed=ranges.Interval[0 none]
    let current=proofs.Context[env relation_context]
    let stale=hir.node_at(nodes {names[id(queries[5])]})
    $runtime_assert stale is? hir.Index
    let rejected=checks.check_index(stale observed none state current [] srcfile @registry symbolic=false)
    $runtime_assert rejected is? Error
    let method_rejected=checks.check_method_index('pop' {names[id(i)]} observed state {array.binding_id} ranges.Interval[0 1024] false current [] srcfile @registry symbolic=false)
    $runtime_assert method_rejected is? Error
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
