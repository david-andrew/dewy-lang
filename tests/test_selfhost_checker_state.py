"""Checker ABI, stable IDs, scope layouts and selective nested-state restoration."""
import subprocess
from pathlib import Path

import pytest
from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
# Independent field widths: do not derive the expected ABI from either twin.
LAYOUTS = {
    'Local': 'name:4 type:4 flags:4 const_init:4 alias:4 owner:4 pos:8 offset:4 env_off:4 vreg:4 outer:4 dloops:4 soa:4 wloop:4',
    'Global': 'name:4 type:4 decl:4 mod:4 sym:8 state:4 is_const:1 init:4 addr:4 fn_written:1 init_written:1 fn_accessed:1 exposed:1',
    'Capture': 'outer:4 inner:4',
    'FnInst': 'decl:4 body:4 targs:8 ptypes:8 params:8 ret:4 sym:8 state:4 kind:4 has_env:1 task_api:1 caps:8 env_size:4 mod:4 partial:4 target:4 locals:8 fntype:4 cabi:1 deterministic:1 parallel_api:1 atomic_api:1 write_sites:8 writes_ready:1 no_indexes:1 no_user_globals:1 noinline:1 gdepth:4 export_name:8 aux_void:1 clib:8 csym:8 cvariadic:4 use_pos:8 made_in:4 pack:8 pack_n:8 pack_k:8',
    'FnSig': 'contract:4 ntp:4 nexplicit:4 params:8 ret:4 mutmask:4 generic:1 done:1',
    'DeclInfo': 'insts:8 sig:40',
    'FnInstanceKey': 'decl:8 args:8',
    'FnCtx': 'inst:4 parent:4 ret:4 infer_ret:1 loop_depth:4 mod:4 floor:4',
    'CheckerScope': 'names:8 syms:8 prev:8 top:8',
    'RefineBindings': 'fields:8 formals:8 self:8 base_type:8',
}


def driver():
    lines, expected = ['main = ():'], []
    for index, (name, spec) in enumerate(LAYOUTS.items()):
        offset, alignment, offsets = 0, 1, []
        fields = [item.split(':') for item in spec.split()]
        for _, width in fields:
            width = int(width)
            a = min(8, width)
            alignment = max(alignment, a)
            offset = (offset + a - 1) // a * a
            offsets.append(offset)
            offset += width
        size = (offset + alignment - 1) // alignment * alignment
        v = f'v{index}'
        lines += [f'    {v} = {name}()', f'    print("{{size_of({name})}} {{align_of({name})}}")',
                  '    print("' + ' '.join(f'{{int(&{v}.{f}) - int(&{v})}}' for f, _ in fields) + '")']
        expected += [f'{size} {alignment}', ' '.join(map(str, offsets))]
    lines += ['    fns = [FnInst()]', '    ctxs = [FnCtx(inst = 0)]',
              '    bindings = RefineBindings(fields = [3], formals = [5], self = 5, base_type = 9)',
              '    saved_formals = bindings.formals', '    saved_self = bindings.self',
              '    cx = 0', '    saved_cx = cx',
              '    loop i in [0..200):', '        fns.push(FnInst(decl = i32(i + 1), caps = [Capture(i32(i), 1)]))',
              '        ctxs.push(FnCtx(inst = i32(i + 1), parent = i32(cx)))', '        cx += 1',
              '    bindings.formals = [8, 13]', '    bindings.self = 13',
              '    fns[0].locals.push(77)', '    ctxs.truncate(saved_cx + 1)', '    cx = saved_cx',
              '    bindings.formals = saved_formals', '    bindings.self = saved_self',
              '    print("{fns.len()} {fns[200].decl} {fns[200].caps[0].outer} {fns[0].locals} {cx} {ctxs.len()}")',
              '    print("{bindings.fields} {bindings.formals} {bindings.self} {bindings.base_type}")',
              '    old = fns', '    fns[200].caps[0].inner = 99',
              '    print("{old[200].caps[0].inner} {fns[200].caps[0].inner}")']
    expected += ['201 200 199 [77] 0 1', '[3] [5] 5 9', '1 99']
    return '\n'.join(lines) + '\n', '\n'.join(expected) + '\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_state_twins(compiler, tmp_path, release):  # noqa: F811
    body, expected = driver()
    for extension in ('dewy', 'jo'):
        (tmp_path / f'checker_state.{extension}').write_text((ROOT / 'compiler' / f'checker_state.{extension}').read_text())
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(f"use 'checker_state.{extension}'\n" + body)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == expected


@pytest.mark.core_quick
def test_checker_state_ships_dewy(compiler):  # noqa: F811
    assert b'/compiler/checker_state.dewy\0' in compiler.read_bytes()
