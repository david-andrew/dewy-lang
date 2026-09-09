"""Native representation/type views agree with hosted queries, independent of arena ids."""

import subprocess
from pathlib import Path

from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_type_queries_match_hosted(tmp_path):
    literal = ty.IntegerLiteralType
    strings = ty.union(ty.StringLiteralType('x'), ty.StringLiteralType('y'))
    address = ty.addr_type()
    extra_address = ty.RefinedType(address.base, (*address.propositions, ty.Proposition('self', '<?', 20)))
    cases = [
        'none', 'void', 'never', 'int', 'uint', 'int8', 'uint64', 'string',
        ty.StringType(4), ty.StringLiteralType('a'), literal(1), strings,
        ty.union(literal(1), literal(20), literal(-3)), ty.union(literal(1), ty.StringLiteralType('x')),
        ty.optional(strings), ty.optional('int64'), ty.union('none', 'int64', 'bool'),
        address, extra_address, ty.nat_type('nat'), ty.nat_type('nat8'),
        ty.optional(extra_address), ty.union(address, 'int64', 'none'),
        ty.ArrayType('int64', None), ty.dict_type('string', 'int64'), ty.set_type('int64'),
        ty.total_dict_type(strings, 'int64'),
        ty.FunctionType([], [], None, 'int64'),
        ty.FunctionType([ty.PosOrKwArg('x', 'int64')], [], None, 'int64'),
    ]
    lines, checks, expected = [], [], []
    build = type_builder(lines)
    for index, value in enumerate(cases):
        native = build(value)
        for query in ('string_valued', 'is_addr', 'is_zero_arg_function'):
            checks.append(f'    printl("{index}:{query}|{{views.{query}({native} type_nodes)}}")')
            expected.append(f'{index}:{query}|{str(getattr(ty, query)(value)).lower()}')
        for query in ('strip_result_refinement', 'strip_all_refinements', 'optional'):
            target = build(getattr(ty, query)(value))
            checks.append(f'    printl("{index}:{query}|{{types.same_type(views.{query}({native} @type_nodes) {target} type_nodes)}}")')
            expected.append(f'{index}:{query}|true')
        for query in ('optional_payload', 'total_dict_key'):
            target = getattr(ty, query)(value)
            args = '@type_nodes' if query == 'optional_payload' else 'type_nodes'
            result = f'views.{query}({native} {args})'
            condition = f'{result} is? none' if target is None else f'matches({result} {build(target)} type_nodes)'
            checks.append(f'    printl("{index}:{query}|{{{condition}}}")')
            expected.append(f'{index}:{query}|true')
        for query in ('enum_members', 'runtime_union_members', 'finite_members'):
            members = getattr(ty, query)(value)
            args = '@type_nodes' if query == 'runtime_union_members' else 'type_nodes'
            result = f'views.{query}({native} {args})'
            checks.append(f'    printl("{index}:{query}|{{size({result})}}")')
            expected.append(f'{index}:{query}|{-1 if members is None else len(members)}')
        layout = ty.fixed_integer_bounds(value)
        if layout is not None:
            checks.append(f'    printl("{index}:bounds|{{bounds_text(views.fixed_integer_bounds({native} type_nodes))}}")')
            expected.append(f'{index}:bounds|{layout[0]},{layout[1]}')
    for label, key, value in [('dict', ty.StringType(3), ty.StringLiteralType('fixed')), ('set', 'int64', None)]:
        target = build(ty.set_type(key) if value is None else ty.dict_type(key, value))
        expression = f'views.container_type({build(key)} {"none" if value is None else build(value)} @type_nodes)'
        checks.append(f'    printl("{label}|{{types.same_type({expression} {target} type_nodes)}}")')
        expected.append(f'{label}|true')
    source = tmp_path / 'type_views.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/type_queries.dewy'}" as views
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
matches = (actual:addr? expected:addr nodes:array<types.Type>):>bool => actual isnt? none and types.same_type(actual expected nodes)
size = (items:array<addr> | none):>int64 => if items is? none (-1) else items.length
bounds_text = (value:views.IntegerBounds?):>string => if value is? none 'none' else "{{_bigint_as_string(value.minimum)}},{{_bigint_as_string(value.maximum)}}"
main = ():>int64 => {{
    let type_nodes:array<types.Type> = []
{chr(10).join(lines + checks)}
    # Canonical tag order ignores both source order and the allocation ids.
    let a = types.primitive('int64' @type_nodes)
    let b = types.primitive('bool' @type_nodes)
    let n = types.primitive('none' @type_nodes)
    let first = views.canonical_members([a b n] type_nodes)
    let second = views.canonical_members([n b a] type_nodes)
    $runtime_assert first.length =? 3 and second.length =? 3
    $runtime_assert first[0] =? n and first[0] =? second[0] and first[1] =? second[1] and first[2] =? second[2]
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
