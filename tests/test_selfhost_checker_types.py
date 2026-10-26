"""Shared checker layouts retain their ABI, defaults and owned-array semantics."""
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('checker_tokens', 'checker_types', 'refinement_types')
# Frozen native ABI: each field's width/alignment, independently of either definition.
LAYOUTS = {
    'TypeInfo': 'kind:4 bits:4 sign:1 flags:4 elem:4 args:4 nargs:4 st:4 ref:4 id:4 mutmask:4 size:4 align:4 mod:4 rep:4',
    'Field': 'name:4 type:4 offset:4 defval:4 boxed:1',
    'Variant': 'name:4 fields:4 nfields:4 tag:4 value:8',
    'StructInfo': 'drop_fn:4 decl:4 targs:4 ntargs:4 fields:4 nfields:4 variants:4 nvariants:4 payload_off:4 simple_enum:1 resolving:1 resolved:1 type:4 name:8 union_:1 soa_:1 record_:1 boxes_done:1 lit_set:4',
    'RefTerm': 'kind:8 value:8 unsigned:1 path:8 offset:8',
    'RefAtom': 'op:4 a:40 b:40',
    'FactBound': 'lo:8 hi:8 nz:1 reason:4 witness:8 wide:1',
    'FactTerm': 'op:4 a:8 b:8 origin:8 type:8 slot:8',
    'FactRequest': 'node:8 owner:8',
}


def layout_driver():
    lines, expected = ['main = ():'], []
    for index, (name, spec) in enumerate(LAYOUTS.items()):
        fields = [(f, int(width)) for f, width in (item.split(':') for item in spec.split())]
        offsets, offset, alignment = [], 0, 1
        for _, width in fields:
            a = min(8, width)
            alignment = max(alignment, a)
            offset = (offset + a - 1) // a * a
            offsets.append(offset)
            offset += width
        size = (offset + alignment - 1) // alignment * alignment
        var = f'v{index}'
        lines += [f'    {var} = {name}()',
                  f'    print("{{size_of({name})}} {{align_of({name})}}")',
                  '    print("' + ' '.join(f'{{int(&{var}.{f}) - int(&{var})}}' for f, _ in fields) + '")']
        expected += [f'{size} {alignment}', ' '.join(map(str, offsets))]
    lines += ['    b = FactBound()', '    t = FactTerm()', '    a = RefAtom()',
              '    print("{b.lo} {b.hi} {b.nz} {int(b.reason)} {b.witness} {b.wide}")',
              '    print("{int(t.op)} {t.a} {t.b} {t.origin} {t.type} {t.slot}")',
              '    print("{int(a.op)} {a.a.kind} {a.a.value} {a.a.unsigned} {a.a.path} {a.a.offset} {a.b.path}")',
              '    a.a.path = [2, 9]', '    xs = [a]', '    copy = xs',
              '    xs[0].a.path.push(11)', '    xs[0].b.value = -7',
              '    print("{copy[0].a.path} {copy[0].b.value} {xs[0].a.path} {xs[0].b.value}")',
              '    print("{FACT_MIN} {FACT_MAX}")']
    expected += ['-9223372036854775808 9223372036854775807 false 0 0 false',
                 '0 0 0 0 0 -1', '0 0 0 false [] 0 []', '[2, 9] 0 [2, 9, 11] -7',
                 '-9223372036854775808 9223372036854775807']
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_layout_twins(compiler, tmp_path, release):  # noqa: F811
    body, expected = layout_driver()
    for extension in ('dewy', 'jo'):
        # Copy the tiny dependency closure so the twin never indirectly loads a Dewy definition.
        for module in MODULES:
            text = (ROOT / 'compiler' / f'{module}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{module}.{extension}').write_text(text)
        source = tmp_path / 'driver.jo'
        source.write_text(''.join(f"use '{m}.{extension}'\n" for m in MODULES) + body)
        binary = tmp_path / 'driver'
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected



def test_shared_enum_ordinals():
    from tests.test_selfhost_twins import dewy_enumerations, jo_enums
    for module in MODULES:
        enums = dewy_enumerations((ROOT / 'compiler' / f'{module}.dewy').read_text())
        assert enums == jo_enums((ROOT / 'compiler' / f'{module}.jo').read_text())
