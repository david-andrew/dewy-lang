"""Native inclusive/exclusive slice boundaries agree with the hosted rules."""
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
LOC = Span(0, 0)


def test_native_slice_checks_match_hosted(tmp_path):
    registry = bindings.BindingRegistry()

    def reference(name, type_):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = type_
        return hir.ExpressedIdentifier(LOC, type_, name, binding_id=binding.id)

    i = reference('i', 'int64')
    text = reference('text', ty.StringType(None))
    sequences = [text, hir.String(LOC, ty.StringLiteralType('abcd'), 'abcd'), hir.String(LOC, ty.StringLiteralType(''), '')]
    constants = {n: hir.Integer(LOC, ty.IntegerLiteralType(n), '0d', n) for n in [-1, 0, 1, 3, 4]}
    queries = []
    for sequence in sequences:
        length = hir.StringLength(LOC, 'int64', sequence)
        for left, right in [(None, None), (constants[0], None), (None, constants[0]),
                            (constants[-1], constants[0]), (constants[0], constants[3]),
                            (constants[0], constants[4]), (constants[3], constants[1]),
                            (i, None), (None, i), (i, i), (length, None), (constants[0], length)]:
            for delimiters in ['[]', '[)', '(]', '()']:
                queries.append(hir.StringSlice(LOC, ty.StringType(None), sequence, hir.Range(LOC, 'range', delimiters, None, left, right)))
    root = hir.Block(LOC, 'void', queries, False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root)
    validator.max_length = 1024
    interval = bounds.Interval
    states = [{}, {i.binding_id: interval(0, 4), bounds._length_key(text.binding_id): interval(5, 8)},
              {i.binding_id: interval(0, None), bounds._length_key(text.binding_id): interval(0, 8),
               bounds._order_key(i.binding_id, bounds._length_key(text.binding_id)): interval(0, None)}]
    expected, checks = [], []
    type_lines = []
    build = type_builder(type_lines)
    hir_lines, _, names = emit_hir(root, type_value=build, with_names=True)
    binding_lines = [f'    registry.by_id[{b.id}]=bindings.Binding[{b.id} {json.dumps(b.name)} "value" span value_type={build(b.type)}]' for b in registry.by_id.values()]
    for state in states:
        entries = []
        for key, value in state.items():
            lo = 'none' if value.lower is None else f'({value.lower})'
            hi = 'none' if value.upper is None else f'({value.upper})'
            entries.append(f'    flow.put(@state {fact(key)[0].replace("facts.", "flow.")} ranges.Interval[{lo} {hi}])')
        for query in queries:
            known = validator._string_length(query.string.type)
            left = interval.exact(0) if query.range.left is None else validator._eval(query.range.left, dict(state), validate=False)
            right = (None if known is None else interval.exact(known - 1)) if query.range.right is None else validator._eval(query.range.right, dict(state), validate=False)
            try:
                validator._validate_string_slice(query, left, right, known, dict(state))
                expected.append('true')
            except UserError:
                expected.append('false')
        checks.append('    state.clear\n' + '\n'.join(entries) + '\n    run(cases state @data)')
    imports = '\n'.join(f'import p"{ROOT / "dewy/bootstrap/semantic" / path}" as {alias}' for alias, path in [
        ('hir', 'hir.dewy'), ('types', 'ty.dewy'), ('bindings', 'bindings.dewy'), ('facts', 'propositions.dewy'),
        ('values', 'analyze/value_bounds.dewy'), ('predicates', 'analyze/predicate_facts.dewy'),
        ('flow', 'analyze/fact_state.dewy'), ('ranges', 'analyze/intervals.dewy'),
        ('intervals', 'analyze/expression_intervals.dewy'), ('relations', 'analyze/relations.dewy'),
        ('slices', 'analyze/slice_checks.dewy'),
    ])
    source = tmp_path / 'slices.dewy'
    source.write_text(f'''from reporting import Span, SrcFile
{imports}
let run=(cases:array<addr> state:flow.State @data:predicates.Data):>void=>{{
    data.snapshot=intervals.Snapshot[]
    loop id in 0.. and id <? data.env.nodes.length {{intervals.record(@data.snapshot id state data.env @data.registry)}}
    loop id in cases {{
        let node=hir.node_at(data.env.nodes id)
        $runtime_assert node is? hir.StringSlice
        printl(slices.check(node state SrcFile['fixture' ''] @data) is? none)
    }}
}}
main=():>int64=>{{
    let span=Span[0 0]
    let nodes:array<hir.AST>=[]
    let type_nodes:array<types.Type>=[]
    let registry=bindings.Registry[]
{chr(10).join(type_lines + hir_lines + binding_lines)}
    let env=values.Environment[nodes type_nodes registry 1024]
    let data=predicates.Data[env relations.Context[flow.Context[1024]] intervals.Snapshot[] registry]
    let state:flow.State=[]
    let cases:array<addr>=[{' '.join(names[id(q)] for q in queries)}]
{chr(10).join(checks)}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines() == expected
