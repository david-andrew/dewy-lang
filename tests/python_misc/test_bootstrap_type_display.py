"""Native diagnostic spellings preserve the hosted type and proof vocabulary."""

import subprocess
from pathlib import Path

from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from dewy.semantic.hir_display import type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_type_display_matches_hosted(tmp_path):
    p = ty.Proposition
    address = ty.addr_type()
    named = ty.NamedType('Node', 73)
    named.resolve(ty.ObjectType([ty.ObjectField('next', ty.optional(named))]))
    fn = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'bool')
    dimension = ty.DimensionType((('Length', 1), ('Time', -2)))
    cases = [
        'none', 'void', 'never', 'any', 'int64', ty.TypeVariable('T'), named,
        ty.IntegerLiteralType(-(1 << 120)), ty.RationalLiteralType(-7, 3),
        ty.StringLiteralType('quote"\u0301 slash\\\u0301 {\u0301x}\n\r\t\b\f\0\x01é😀'),
        ty.BinaryLiteralType(bytes(range(256))), ty.PathType([]), ty.PathLiteralType('a{b}".dewy'),
        ty.ModuleType(()), ty.MetaType(ty.ObjectType([])),
        ty.StringType(), ty.StringType(4), ty.ArrayType('int64', None), ty.ArrayType('bool', 0),
        dimension, ty.DimensionType(()), ty.QuantityType(ty.union('int', 'float'), dimension),
        ty.TypeAnd(['int', ty.TypeOr(['bool', 'float'])]), ty.TypeNot('bool'), ty.TypeNot(ty.TypeNot('bool')),
        ty.TypeNot(ty.TypeOr(['int', 'bool'])),
        ty.TypeParameterize(ty.TypeOr(['A', 'B']), ['int64', 'bool']),
        ty.SequenceType(['int64', 'bool']), fn,
        ty.FunctionType([], [], None, 'void'),
        ty.FunctionType([ty.PosOrKwArg('xs', ty.ArrayType('int64', None), place=True)],
                        [ty.KwOnlyArg('count', 'int64', False, place=True)], 'rest', 'void',
                        (ty.GenericParam('T'), ty.GenericParam('U', 'int'))),
        ty.OverloadType([fn, ty.FunctionType([], [], None, 'void')]),
        ty.ObjectType([ty.ObjectField('start', 'int64', mutable=False),
                       ty.ObjectField('stop', 'int64', refinement=(p('self', '>=?', 0, term='start', term_of='value'),))], immutable=True),
        ty.dict_type('string', 'int64'), ty.set_type('int64'),
        ty.total_dict_type(ty.union(ty.StringLiteralType('a'), ty.StringLiteralType('b')), 'bool'),
        address, ty.RefinedType(address.base, (*address.propositions, p('self', '<?', 20))),
        *(ty.nat_type(name) for name in ty.NAT_BASES),
        ty.RefinedType('int64', (p('self', 'not=?', 0), p('self', '<=?', 0, term='src'))),
        ty.RefinedType(ty.ArrayType('int64', None), (p('length', '>=?', 2),)),
        ty.RefinedType('void', (p('@src', 'is?', 0, type_='string'), p('.end', '<=?', 0, term='src', of='length'))),
        ty.RefinedType('bool', (p('@x', 'is?', 0, type_='int64', when=True), p('@x', 'isnt?', 0, type_='int64', when=False), p('@n', '>=?', 0))),
        ty.RefinedType('bool', (p('@x', 'is?', 0, type_='int64', when=True),)),
        ty.RefinedType('int64', (p('self', '>=?', 1), p('@src', '>=?', 0, of='length'))),
        ty.RefinedType('int64', (ty.ADDR_PROPOSITION,)),
    ]
    lines = []
    build = type_builder(lines)
    ids = [build(value) for value in cases]
    source = tmp_path / 'type_display.dewy'
    source.write_text(f'''
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
main = ():>int64 => {{
    let type_nodes:array<types.Type> = []
{chr(10).join(lines)}
    loop id in [{' '.join(ids)}] {{ printl(display.type_to_dewy(id type_nodes)) }}
    let mint = types.object_type([] 'Example' false [] [] @type_nodes minted=true)
    printl(display.type_to_dewy(mint type_nodes))
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [type_to_dewy(value) for value in cases] + ['Example']
