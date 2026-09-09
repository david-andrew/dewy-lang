"""Compare the native effect fixed point with hosted analysis on checked HIR."""

import dataclasses
import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from dewy.semantic.analyze.effects import analyze_effects
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)
ARRAY = ty.ArrayType('int64')
CALLABLE = ty.FunctionType([], [], None, 'void')


def effect_program():
    declarations = []

    def read(binding_id, value_type=ARRAY):
        return hir.ExpressedIdentifier(LOC, value_type, f'p{binding_id}', binding_id=binding_id)

    def number(n=0):
        return hir.Integer(LOC, 'int64', '0d', n)

    def function(binding_id, params, body):
        literal = hir.FunctionLiteral(LOC, CALLABLE, params, [], None, 'void', hir.Block(LOC, 'void', body, True))
        declarations.append(hir.Declare(LOC, 'void', 'let', f'f{binding_id}', CALLABLE, literal, binding_id=binding_id))
        return literal

    def param(binding_id, value_type=ARRAY):
        return hir.Param(f'p{binding_id}', value_type, binding_id=binding_id, place=True)

    def call(binding_id, args, selected=None):
        return hir.FunctionCall(LOC, 'void', read(binding_id, CALLABLE), args, {}, selected_method_index=selected)

    def place(node):
        return hir.Place(LOC, node.type, node)

    def store(node):
        return hir.IndexAssign(LOC, 'void', hir.Index(LOC, 'int64', node, number(), 0), number(42))

    function(101, [param(1)], [store(read(1))])
    function(102, [param(2)], [call(101, [read(2)])])  # value boundary: only a caller read
    function(103, [param(3)], [call(101, [place(read(3))])])
    record_type = ty.ObjectType((ty.ObjectField('items', ARRAY),))
    function(104, [param(4, record_type)], [call(101, [place(hir.MemberAccess(LOC, ARRAY, read(4, record_type), 'items'))])])
    function(105, [param(5)], [hir.ArrayLength(LOC, 'int64', read(5))])
    function(106, [param(6)], [call(107, [place(read(6))])])
    function(107, [param(7)], [store(read(7)), call(106, [place(read(7))])])
    function(108, [param(8, CALLABLE), param(9)], [hir.FunctionCall(LOC, 'void', read(8, CALLABLE), [place(read(9))], {})])

    mutator = function(109, [param(10)], [store(read(10))])
    reader = function(110, [param(11)], [hir.Index(LOC, 'int64', read(11), number(), 0)])
    overloaded = hir.OverloadedFunction(LOC, ty.OverloadType([CALLABLE, CALLABLE]), [mutator, reader])
    declarations.append(hir.Declare(LOC, 'void', 'let', 'overloaded', overloaded.type, overloaded, binding_id=111))
    function(112, [param(12)], [call(111, [place(read(12))], selected=1)])
    function(113, [param(13)], [call(111, [place(read(13))])])  # no selection: conservatively merge
    callback_record = ty.ObjectType((ty.ObjectField('callback', CALLABLE),))
    function(114, [param(14, callback_record)], [hir.MemberAccess(LOC, CALLABLE, read(14, callback_record), 'callback')])
    dictionary = ty.dict_type('int64', 'int64')
    keys = hir.MemberAccess(LOC, ARRAY, read(15, dictionary), 'keys')
    values = hir.MemberAccess(LOC, ARRAY, read(15, dictionary), 'values')
    function(115, [param(15, dictionary), param(16, 'int64')], [hir.DictStore(LOC, 'void', keys, values, read(16, 'int64'), number(1))])
    function(116, [param(17)], [hir.RepresentationCast(LOC, ARRAY, read(17))])
    function(117, [param(18, 'int64')], [hir.Index(LOC, 'int64', read(500), read(18, 'int64'), None)])

    # A recursive place through a field would produce infinitely deep routes
    # without the common finite-depth abstraction.
    recursive = ty.ObjectType((ty.ObjectField('next', 'any'), ty.ObjectField('value', 'int64')))
    function(118, [param(19, recursive)], [
        hir.MemberAssign(LOC, 'void', hir.MemberAccess(LOC, 'int64', read(19, recursive), 'value'), number()),
        call(118, [place(hir.MemberAccess(LOC, recursive, read(19, recursive), 'next'))]),
    ])
    # A rebound callable cannot retain its former direct-call summary.
    declarations.append(hir.Declare(LOC, 'void', 'let', 'alias', CALLABLE, read(101, CALLABLE), binding_id=119))
    declarations.append(hir.Assign(LOC, 'void', read(119, CALLABLE), '=', read(110, CALLABLE)))
    function(120, [param(20)], [call(119, [place(read(20))])])
    return hir.Block(LOC, 'void', declarations, True)


def emit_hir(root, *, type_value=None, with_names=False):
    """Write a checked-HIR fixture using arena references, retaining sharing.

    Only callable classification affects this analysis. Other type metadata
    is represented by `any`; the test exercises effects, not type checking.
    """
    lines = []
    memo = {}

    def value(item, field=None):
        if isinstance(item, hir.AST):
            return node(item)
        if field in ('type', 'rettype', 'exception_type', 'refined'):
            if type_value is not None:
                return type_value(item)
            return 'callable' if isinstance(item, (ty.FunctionType, ty.OverloadType)) else 'scalar'
        if field == 'annotation':
            return 'none' if item is None else value(item, 'type')
        if field == 'object_type' and item is not None:
            return type_value(item)
        if field == 'object_fields':
            return '[' + ' '.join(f'hir.FieldBinding[{binding} {json.dumps(name)}]' for binding, name in item) + ']'
        if isinstance(item, SrcFile):
            return 'srcfile'
        if item is None:
            return 'none'
        if isinstance(item, bool):
            return str(item).lower()
        if isinstance(item, int):
            return str(item) if item >= 0 else f'({item})'
        if isinstance(item, str):
            return json.dumps(item)
        if isinstance(item, Span):
            return 'span'
        if isinstance(item, hir.Param):
            props = ' '.join(f'{"value_type" if f.name == "type" else f.name}={value(getattr(item, f.name), f.name)}' for f in dataclasses.fields(item))
            return f'hir.{type(item).__name__}[{props}]'
        if isinstance(item, hir.ObjectField):
            props = ' '.join(f'{f.name}={value(getattr(item, f.name), f.name)}' for f in dataclasses.fields(item))
            return f'hir.ObjectField[{props}]'
        if isinstance(item, (list, tuple)):
            return '[' + ' '.join(value(child) for child in item) + ']'
        if isinstance(item, dict):
            return '[' + ' '.join(f'{json.dumps(k)} -> {value(v)}' for k, v in item.items()) + ']'
        raise TypeError((item, field))

    def node(item):
        if id(item) in memo:
            return memo[id(item)]
        props = ' '.join(f'{"value_type" if f.name == "type" else f.name}={value(getattr(item, f.name), f.name)}' for f in dataclasses.fields(item))
        name = f'n{len(memo)}'
        memo[id(item)] = name
        lines.append(f'    let {name} = hir.append_node(@nodes hir.{type(item).__name__}[{props}])')
        return name

    root_id = node(root)
    return (lines, root_id, memo) if with_names else (lines, root_id)


def test_native_effect_analysis_matches_hosted(tmp_path):
    root = effect_program()
    expected = analyze_effects(root)
    lines, root_id = emit_hir(root)
    source = tmp_path / 'effects.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/effects.dewy'}" as effects
emit = (binding_id:addr kind:string routes:array<effects.Route>):>void => {{
    loop route in routes {{ printl("{{binding_id}}|{{kind}}|{{route.steps.join('.')}}") }}
}}
main = ():>int64 => {{
    let span = Span[0 0]
    let nodes:array<hir.AST> = []
    let type_nodes:array<types.Type> = []
    let scalar = types.primitive('any' @type_nodes)
    let callable = types.function_type([] [] none scalar [] @type_nodes)
{chr(10).join(lines)}
    let program = effects.analyze_effects({root_id} nodes type_nodes)
    loop binding_id in program.by_param_binding.keys {{
        if binding_id not in? program.by_param_binding continue
        let summary = program.by_param_binding[binding_id]
        emit(binding_id 'read' summary.reads)
        emit(binding_id 'mutate' summary.mutates)
        emit(binding_id 'rebind' summary.rebinds)
        emit(binding_id 'escape' summary.escapes)
    }}
    return 0
}}
''')
    output = tmp_path / 'effects.udewy'
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], check=False, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    rows = []
    for binding_id, summary in expected.by_param_binding.items():
        for kind, routes in [('read', summary.reads), ('mutate', summary.mutates), ('rebind', summary.rebinds), ('escape', summary.escapes)]:
            rows.extend(f'{binding_id}|{kind}|{".".join(route)}' for route in routes)
    assert sorted(result.stdout.splitlines()) == sorted(rows)
