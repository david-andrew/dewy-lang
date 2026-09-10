"""Native numeric materialization retains exact values and canonical limbs."""
import subprocess
from pathlib import Path

from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
VALUES = [0, 1, -1, 2**32 - 1, 2**32, -(2**63), 2**64 - 1, 2**100 + 17, -(2**160 + 2**64 + 9)]


def test_native_numeric_limb_materialization(tmp_path):
    lines = []
    build = type_builder(lines)
    big = build(ty.TypeOr([ty.IntegerLiteralType(0), ty.ObjectType((
        ty.ObjectField('sign', 'int64'), ty.ObjectField('limbs', ty.ArrayType('uint64', None)),
    ))]))
    source = tmp_path / 'numeric_values.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/numeric_values.dewy'}" as numeric
main = ():>int64 => {{
    let type_nodes:array<types.Type>=[]
{chr(10).join(lines)}
    let session=contexts.Session[types=type_nodes]
    let values:array<bigint>=[{' '.join(f'({value})' for value in VALUES)}]
    loop value in values {{
        let id=numeric.bigint_literal(value {big} Span[0 0] @session)
        let node=hir.node_at(session.hir id)
        if node is? hir.Integer {{printl('0:0:') continue}}
        $runtime_assert node is? hir.ObjectLiteral and node.fields.length =? 2 and node.integer_value isnt? none
        let sign=hir.node_at(session.hir node.fields[0].value)
        let limbs=hir.node_at(session.hir node.fields[1].value)
        $runtime_assert sign is? hir.Integer and limbs is? hir.ArrayLiteral
        let parts:array<string>=[]
        loop item in limbs.items {{
            let limb=hir.node_at(session.hir item)
            $runtime_assert limb is? hir.Integer
            parts.push(_bigint_as_string(limb.value))
        }}
        printl("{{_bigint_as_string(node.integer_value)}}:{{_bigint_as_string(sign.value)}}:{{parts.join(',')}}")
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    expected = []
    for value in VALUES:
        magnitude, limbs = abs(value), []
        while magnitude:
            limbs.append(str(magnitude & 0xffffffff))
            magnitude >>= 32
        expected.append(f'{value}:{0 if value == 0 else -1 if value < 0 else 1}:{",".join(limbs)}')
    assert result.stdout.splitlines() == expected
