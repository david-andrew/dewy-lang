"""Run source-order initialization in Dewy against the hosted HIR analysis."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.analyze.initialization import validate_initialization
from dewy.semantic.errors import NotImplementedYet, UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]

CASES = [
    'later(); let later = ():>int64 => 42',
    'let first = ():>int64 => later()\nfirst();\nlet later = ():>int64 => 42',
    'let first = ():>int64 => later()\nlet later = ():>int64 => 42\nlet main = ():>int64 => first()',
    'let first = ():>int64 => if false later() else 42\nfirst();\nlet later = ():>int64 => 0',
    'let flag:bool = true\nlet first = ():>int64 => if flag later() else 42\nfirst();\nlet later = ():>int64 => 0',
    'let invoke = (fn:<():>int64>):>int64 => fn()\nlet ready = ():>int64 => 42\ninvoke(@ready);\nlet unrelated = ():>int64 => 0',
    'let invoke = (fn:<():>int64>):>int64 => fn()\nlet first = ():>int64 => later()\ninvoke(@first);\nlet later = ():>int64 => 42',
    'let invoke = (fn:<():>int64>):>int64 => fn()\nlet relay = (fn:<():>int64>):>int64 => invoke(@fn)\nlet ready = ():>int64 => 42\nrelay(@ready);',
    'let even = ():>int64 => odd()\nlet odd = ():>int64 => even()\nlet main = ():>int64 => even()',
    'let f = (x:int64=later()):>int64 => x\nlet later = ():>int64 => 42',
    'let ready = ():>int64 => 42\nlet f = (x:int64=ready()):>int64 => x\nlet main = ():>int64 => f()',
    'let make = ():><():>int64> => @later\nmake()();\nlet later = ():>int64 => 42',
    'let main:int64 = 42',
    'let main = (x:int64):>int64 => x',
    'let main = ():>bool => true',
    'let main = (args:array<string>):>int64 => 0',
    'let main = ():>void => void',
]


def type_builder(lines):
    """Preserve the type shapes consulted by initialization (including main)."""
    cache = {}

    def optional(value):
        return 'none' if value is None else json.dumps(value, ensure_ascii=False).replace('{', r'\{')

    def propositions(items):
        return ' '.join(
            'facts.Proposition['
            f'subject={json.dumps(p.subject)} op={json.dumps(p.op)} value=({p.value}) '
            f'projection={json.dumps(p.of)} term={optional(p.term)} term_id={optional(p.term_id)} '
            f'term_projection={json.dumps(p.term_of)} tested_type={"none" if p.type_ is None else build(p.type_)} '
            f'when={optional(p.when)} subject_id={optional(p.subject_id)} axiom={optional(p.axiom)}]'
            for p in items
        )

    def build(value):
        key = repr(value)
        if key in cache:
            return cache[key]
        if isinstance(value, str):
            call = f'types.primitive({json.dumps(value)} @type_nodes)'
        elif isinstance(value, ty.GenericTypeAlias):
            params = ' '.join(f'types.GenericParam[{optional(p.name)} {build(p.bound)}]' for p in value.params)
            call = f'types.GenericTypeAlias[[{params}] {build(value.body)}]'
        elif isinstance(value, ty.IntegerLiteralType):
            call = f'types.integer_literal(({value.value}) @type_nodes)'
        elif isinstance(value, ty.StringLiteralType):
            call = f'types.string_literal({optional(value.value)} @type_nodes)'
        elif isinstance(value, ty.BinaryLiteralType):
            call = f'types.binary_literal([{" ".join(map(str, value.value))}] @type_nodes)'
        elif isinstance(value, ty.RationalLiteralType):
            call = f'types.rational_literal(({value.numerator}) ({value.denominator}) @type_nodes)'
        elif isinstance(value, ty.PathLiteralType):
            call = f'types.path_type({optional(value.value)} [] @type_nodes)'
        elif isinstance(value, ty.PathType):
            call = 'types.path_type(none [] @type_nodes)'
        elif isinstance(value, ty.TypeVariable):
            call = f'types.type_variable({optional(value.name)} {build(value.bound)} @type_nodes)'
        elif isinstance(value, ty.NamedType):
            call = f'types.named_type({optional(value.name)} {len(cache)} @type_nodes)'
        elif isinstance(value, ty.MetaType):
            call = f'types.meta_type({build(value.family)} @type_nodes)'
        elif isinstance(value, ty.ModuleType):
            fields = ' '.join(f'types.ModuleField[{optional(f.name)} {build(f.type)} {f.binding_id} {"none" if f.type_value is None else build(f.type_value)}]' for f in value.fields)
            call = f'types.module_type([{fields}] @type_nodes)'
        elif isinstance(value, ty.DimensionType):
            powers = ' '.join(f'types.DimensionPower[{optional(name)} ({power})]' for name, power in value.powers)
            call = f'types.dimension([{powers}] @type_nodes)'
        elif isinstance(value, ty.QuantityType):
            call = f'types.quantity_type({build(value.number)} {build(value.dimension)} @type_nodes)'
        elif isinstance(value, ty.TypeNot):
            inner = build(value.type)
            call = f'types.intern(@type_nodes types.TypeNot[key="not-{inner}" item={inner}])'
        elif isinstance(value, ty.TypeParameterize):
            call = f'types.parameterize({build(value.t)} [{" ".join(build(a) for a in value.args)}] @type_nodes)'
        elif isinstance(value, ty.SequenceType):
            call = f'types.sequence([{" ".join(build(a) for a in value.items)}] @type_nodes)'
        elif isinstance(value, ty.StringType):
            call = f'types.string_type({"none" if value.length is None else value.length} @type_nodes)'
        elif isinstance(value, ty.ArrayType):
            call = f'types.array_type({build(value.element)} {"none" if value.length is None else value.length} @type_nodes)'
        elif isinstance(value, ty.RefinedType):
            call = f'types.refined_type({build(value.base)} [{propositions(value.propositions)}] @type_nodes)'
        elif isinstance(value, ty.FunctionType):
            pos = ' '.join(f'types.PosOrKwArg[{"none" if p.name is None else json.dumps(p.name)} {build(p.type)} {str(p.required).lower()} {str(p.place).lower()}]' for p in value.pos_or_kw)
            kw = ' '.join(f'types.KwOnlyArg[{json.dumps(p.name)} {build(p.type)} {str(p.required).lower()} {str(p.place).lower()}]' for p in value.kw_only)
            params = ' '.join(f'types.GenericParam[{json.dumps(p.name)} {build(p.bound)}]' for p in value.type_params)
            call = f'types.function_type([{pos}] [{kw}] {"none" if value.rest is None else json.dumps(value.rest)} {build(value.ret)} [{params}] @type_nodes)'
        elif isinstance(value, ty.OverloadType):
            call = f'types.overload_type([{" ".join(build(m) for m in value.methods)}] @type_nodes)'
        elif isinstance(value, ty.ObjectType):
            fields = ' '.join(f'types.ObjectField[name={json.dumps(f.name)} value_type={build(f.type)} mutable={str(f.mutable).lower()} refinement=[{propositions(f.refinement)}]]' for f in value.fields)
            call = f'types.object_type([{fields}] {"none" if value.brand is None else json.dumps(value.brand)} {str(value.immutable).lower()} [] [] @type_nodes)'
        elif isinstance(value, (ty.TypeOr, ty.TypeAnd)):
            call = f'types.{"union" if isinstance(value, ty.TypeOr) else "intersect"}([{" ".join(build(m) for m in value.items)}] @type_nodes)'
        else:
            raise TypeError(value)
        name = f't{len(cache)}'
        cache[key] = name
        lines.append(f'    let {name} = {call}')
        return name

    return build


def test_native_initialization_matches_hosted(tmp_path):
    functions = []
    expected = []
    for index, body in enumerate(CASES):
        srcfile = SrcFile(None, body)
        root, context = check._typecheck_module(srcfile)
        registry = context.binding_registry
        try:
            validate_initialization(root, registry, srcfile)
            expected.append(f'{index}|ok')
        except (UserError, NotImplementedYet) as error:
            expected.append(f'{index}|{error.report.title}')
        type_lines = []
        build_type = type_builder(type_lines)
        hir_lines, root_id, names = emit_hir(root, type_value=build_type, with_names=True)
        binding_lines = []
        for binding in registry.by_id.values():
            declaration = names.get(id(binding.declaration), 'none')
            function = names.get(id(binding.function), 'none')
            value_type = 'none' if binding.type is None else build_type(binding.type)
            binding_lines.append(f'    registry.by_id[{binding.id}] = bindings.Binding[id={binding.id} name={json.dumps(binding.name)} kind={json.dumps(binding.kind)} loc=span value_type={value_type} declaration={declaration} function={function}]')
        functions.append(f'''
case_{index} = ():>void => {{
    let span = Span[0 0]
    let srcfile = SrcFile['fixture' {json.dumps(body)}]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let registry = bindings.Registry[]
{chr(10).join(type_lines + hir_lines + binding_lines)}
    let result = initialization.validate_initialization({root_id} nodes type_nodes registry srcfile)
    if result is? none {{ printl('{index}|ok') }}
    else {{ printl("{index}|{{result.title}}") }}
}}
''')
    source = tmp_path / 'initialization.dewy'
    source.write_text(f'''from reporting import Span, SrcFile
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/initialization.dewy'}" as initialization
{chr(10).join(functions)}
main = ():>int64 => {{
    {' '.join(f'case_{i}()' for i in range(len(CASES)))}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
