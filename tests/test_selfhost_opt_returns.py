"""Recursive return sinking: frozen differential, guards and IR snapshots."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
render = (code: Ins[]) -> str:
    text = ""
    loop ins in code: text = text + "{ins.op} {ins.ty} {ins.dst} {ins.a} {ins.b} {ins.c} {ins.imm} {ins.pos}\n"
    text

run = (input: Ins[], types0: i8[], fn_index: int = 7) -> Ins[]:
    snapshot = render(input)
    code = input
    types = types0
    opt_ret_sink(code, types, fn_index)
    assert(render(input) == snapshot, "borrowed code preserves a shared snapshot")
    assert(code.len() == input.len(), "instruction count")
    print(render(code))
    code

main = ():
    types = [i8(0), i8(0), i8(1), i8(2), i8(3)]
    assert(run([], []).len() == 0, "empty")
    run([Ins(.ret, a=-1)], [])
    # Both guard predicates, including the original scan's index-one start.
    loop call in [Op.call, Op.calli, Op.callc]:
        loop target in [7, 8]:
            code = [Ins(.block), Ins(call, imm=target), Ins(.mov, dst=1, a=0, pos=17), Ins(.br, pos=23), Ins(.end), Ins(.ret, a=1, pos=29)]
            r = run(code, types)
            changed = call == .call and target == 7
            assert((r[2].op == .nop and r[3].op == .ret) == changed, "recursive direct-call guard")
            if changed: assert(r[3].a == 0 and r[3].pos == 23, "source and branch position")
    run([Ins(.call, imm=7), Ins(.block), Ins(.mov, dst=1, a=0), Ins(.br), Ins(.end), Ins(.ret, a=1)], types)
    run([Ins(.block), Ins(.call, imm=7), Ins(.mov, dst=1, a=0), Ins(.br), Ins(.end), Ins(.nop), Ins(.ret, a=1)], types)
    # All scalar widths, canonical constants, type-changing moves, identity
    # moves, mismatched destinations and void returns.
    loop source in [0..5):
        loop ty in [0..3):
            loop dst in [0, 1]:
                loop ret in [-1, 0, 1]:
                    r = run([Ins(.block), Ins(.call, imm=7), Ins(.mov, i32(ty), i32(dst), i32(source)), Ins(.br, pos=53), Ins(.end), Ins(.ret, a=i32(ret), pos=59)], types)
                    source_ty = int(types[source])
                    if source_ty == 3: source_ty = 0
                    changed = ret >= 0 and dst == ret and ty == source_ty and source != ret
                    assert((r[3].op == .ret) == changed, "same-type return move")
    # A loop branch is a back edge; a block/if branch exits. Out-of-scope
    # branches are unchanged, and adjacent ends may lead to the same return.
    loop kind in [Op.block, Op.loop, Op.if_]:
        loop distance in [0..3):
            r = run([Ins(.block), Ins(kind, a=0), Ins(.call, imm=7), Ins(.mov, dst=1, a=0), Ins(.br, imm=distance, pos=71), Ins(.end), Ins(.end), Ins(.ret, a=1)], types)
            changed = distance == 1 or distance == 0 and kind != .loop
            assert((r[4].op == .ret) == changed, "branch target")
    # Repeated invocation and large stacks/index tables; the frozen twin
    # independently finds the targets and performs the original array writes.
    loop depth in [1, 64, 257]:
        code: Ins[]
        loop i in [0..depth): code.push(Ins(.block))
        code.push(Ins(.call, imm=7))
        code.push(Ins(.mov, dst=1, a=0))
        code.push(Ins(.br, imm=depth - 1, pos=89))
        loop i in [0..depth): code.push(Ins(.end))
        code.push(Ins(.ret, a=1))
        r = run(code, types)
        assert(r[depth + 2].op == .ret, "nested return")
        r2 = run(r, types)
        assert(render(r) == render(r2), "idempotent")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_opt_return_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        for stem in ('ir_types', 'opt_returns'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (tmp_path / f'{stem}.{extension}').write_text(text)
        source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
        source.write_text(f"use 'opt_returns.{extension}'\nuse 'ir_types.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith('ok\n')
