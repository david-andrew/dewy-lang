"""Generic alias application and compile-time transport agree with the seed."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import check, ty
from dewy.semantic.errors import TypeCheckError, UserError
from dewy.semantic.hir_display import type_alias_value_to_dewy, type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_generic_type_aliases(tmp_path):
    t = ty.TypeVariable('T')
    u = ty.TypeVariable('U', t)
    aliases = [
        ty.GenericTypeAlias([ty.GenericParam('T')], t),
        ty.GenericTypeAlias([ty.GenericParam('T', 'int')], ty.ArrayType(t, None)),
        ty.GenericTypeAlias([ty.GenericParam('T'), ty.GenericParam('U', t)],
                            ty.ObjectType([ty.ObjectField('first', t), ty.ObjectField('second', u)])),
        # The inner callable's T shadows the alias's T during substitution.
        ty.GenericTypeAlias([ty.GenericParam('T')], ty.FunctionType(
            [ty.PosOrKwArg('x', t)], [], None, t, [ty.GenericParam('T')],
        )),
        ty.GenericTypeAlias([], 'bool'),
    ]
    cases = [(0, ['string']), (0, []), (0, ['int64', 'bool']),
             (1, ['int8']), (1, ['string']), (2, ['int64', 'int8']),
             (2, ['int8', 'int64']), (2, ['string', ty.StringLiteralType('ok')]),
             (3, ['int64']), (4, []), (4, ['bool'])]
    lines, checks, expected = [], [], []
    build = type_builder(lines)
    native_aliases = [build(alias) for alias in aliases]
    context = SimpleNamespace(srcfile=SrcFile(None, ''), type_system=ty.TypeSystem())
    for alias, name in zip(aliases, native_aliases):
        checks.append(f'    printl(display.type_alias_value_to_dewy({name} type_nodes))')
        expected.append(type_alias_value_to_dewy(alias))
    for index, (which, arguments) in enumerate(cases):
        result = f'aliases.instantiate({native_aliases[which]} [{" ".join(build(arg) for arg in arguments)}] subtyping.default_links @type_nodes source span)'
        checks.append(f'    let result{index} = {result}')
        checks.append(f'    if result{index} is? Error {{ $runtime_assert result{index}.pointers.length >? 0 printl("{{result{index}.title}}|{{result{index}.pointers[0].message}}") }} else {{ printl(display.type_to_dewy(result{index} type_nodes)) }}')
        try:
            value = check._instantiate_type_alias(aliases[which], arguments, loc=Span(0, 0), ctx=context)
        except (TypeCheckError, UserError) as error:
            expected.append(f'{error.report.title}|{error.report.pointer_messages[0].message}')
        else:
            expected.append(type_to_dewy(value))
    module = ty.ModuleType((ty.ModuleField('Box', 'type', 21, aliases[1]),))
    module_id = build(module)
    type_type = build('type')
    source = tmp_path / 'type_aliases.dewy'
    source.write_text(f'''
from reporting import SrcFile, Span, Error
import p"{ROOT / 'dewy/bootstrap/semantic/type_aliases.dewy'}" as aliases
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
import p"{ROOT / 'dewy/bootstrap/semantic/subtyping.dewy'}" as subtyping
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
main = ():>int64 => {{
    let type_nodes:array<types.Type> = []
    let span = Span[0 0]
    let source = SrcFile['fixture' '']
{chr(10).join(lines + checks)}
    # Compile-time values survive module export, registry storage, and HIR.
    let namespace = types.node_at(type_nodes {module_id})
    $runtime_assert namespace is? types.ModuleType
    let export = types.module_field(namespace 'Box')
    $runtime_assert export isnt? none and export.type_value isnt? none
    let registry = bindings.Registry[]
    registry.by_id[21] = bindings.Binding[id=21 name='Box' kind='value' loc=span type_value=export.type_value]
    let bound = bindings.binding_at(registry 21)
    $runtime_assert bound.type_value isnt? none
    let nodes:array<hir.AST> = []
    let id = hir.append_node(@nodes hir.TypeValue[loc=span value_type={type_type} value=bound.type_value name='Box'])
    let node = hir.node_at(nodes id)
    $runtime_assert node is? hir.TypeValue
    printl(display.type_alias_value_to_dewy(node.value type_nodes))
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected + [type_alias_value_to_dewy(aliases[1])]
