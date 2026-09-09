"""Compare all native builtin signatures and active operator spellings."""

import json
import subprocess
from pathlib import Path

from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import builtins
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_builtin_tables_match_hosted(tmp_path):
    type_lines = []
    build_type = type_builder(type_lines)
    expected = [(name, build_type(value)) for name, value in builtins.builtin_types.items()]
    checks = []
    rows = []
    for name, value in expected:
        checks.append(f'    if {json.dumps(name)} not in? actual return 1')
        checks.append(f'    printl("type:{name}|{{types.same_type(actual[{json.dumps(name)}] {value} type_nodes)}}")')
        rows.append(f'type:{name}|true')
    mappings = [
        ('binary', 'binary_operators', builtins.BINOP_DUNDER_MAP),
        ('inverted', 'inverted_comparisons', builtins.INVERTED_COMPARISON_DUNDER_MAP),
        ('prefix', 'prefix_operators', builtins.UNARY_PREFIX_DUNDER_MAP),
        ('postfix', 'postfix_operators', builtins.UNARY_POSTFIX_DUNDER_MAP),
    ]
    for prefix, native, hosted in mappings:
        checks.append(f'''    loop name in builtin.{native}.keys {{
        if name in? builtin.{native} {{ printl("{prefix}:{{name}}|{{builtin.{native}[name]}}") }}
    }}''')
        rows.extend(f'{prefix}:{name}|{value}' for name, value in hosted.items())
    for name in builtins.builtin_type_aliases:
        rows.append(f'alias:{name}|dimension[{name}^1]')
    rows.extend(f'promote:{a},{b}|{result}' for a, b, result in builtins.builtin_promote_rules)
    source = tmp_path / 'builtins.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/builtins.dewy'}" as builtin
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
main = ():>int64 => {{
    let type_nodes:array<types.Type> = []
    let actual = builtin.definitions(@type_nodes)
    if actual.length not=? {len(expected)} return 2
{chr(10).join(type_lines + checks)}
    let aliases = builtin.type_aliases(@type_nodes)
    loop name in aliases.keys {{
        if name in? aliases {{ printl("alias:{{name}}|{{types.describe(aliases[name] type_nodes)}}") }}
    }}
    loop rule in builtin.promotions {{ printl("promote:{{rule.left}},{{rule.right}}|{{rule.result}}") }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert sorted(result.stdout.splitlines()) == sorted(rows)
