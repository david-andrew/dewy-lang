"""Wasm borrowed allocator/import views across growth and metadata replacement."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
main = ():
    wfn_index = [0, 1]
    wasm_grow = [false, false]
    wasm_user_pos = [false]
    loop count in [0, 1, 4, 257, 1024, 3, 0, 513]:
        f = IrFn(vtypes=fill(i8(0), count * 3), kval=fill(0, count * 3))
        # Many simultaneous locals in all groups, then expiration and reuse.
        loop iteration in [0..3):
            loop v in [0..count):
                ty = v % 3
                f.vtypes[v] = i8(ty)
                f.vtypes[v + count] = i8(ty)
                f.vtypes[v + count * 2] = i8(ty)
                f.code.push(Ins(if ty == 0: Op.iconst else: Op.fconst, ty=i32(ty), dst=i32(v), imm=v))
            loop v in [0..count):
                f.code.push(Ins(.mov, ty=i32(v % 3), dst=i32(v + count), a=i32(v)))
            loop v in [0..count):
                f.code.push(Ins(.mov, ty=i32(v % 3), dst=i32(v + count * 2), a=i32(v + count)))
        snapshot = f
        bytes = wasm_body(f)
        assert(snapshot.vtypes == f.vtypes and snapshot.code.len() == f.code.len(), "IR snapshot")
        print("{bytes}:{loc_of}:{wasm_error}")
    loop count in [0, 1, 4, 257, 3, 0, 129]:
        params = fill(WT_I64, count)
        loop k in [0..count):
            if k % 2 == 0: params[k] = WT_I32
        wasm_import_params = [[], params]
        wasm_import_results = [-2, WT_I32]
        frozen = wasm_import_params
        frozen_results = wasm_import_results
        f = IrFn(nparams=count, vtypes=fill(i8(0), count + 1))
        loop k in [0..count): f.args.push(i32(k))
        f.code = [Ins(.call, dst=i32(count), a=0, b=i32(count), imm=1), Ins(.call, dst=-1, a=0, b=i32(count), imm=0), Ins(.ret, a=i32(count))]
        print(wasm_body(f))
        assert(frozen == wasm_import_params and frozen_results == wasm_import_results, "imports preserved")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_wasm_allocator_import_views(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('ir_types', 'ir_operands', 'leb128', 'wasm_emit'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'ir_types.{extension}'\nuse 'wasm_emit.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
