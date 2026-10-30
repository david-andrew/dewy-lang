"""Arm64 allocation/frame differential: pressure, call edges, spill ties and reuse."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''
layouts = ir_operand_layouts()
rng = 714623
random = (n: int) -> int:
    rng = rng * 6364136223846793005 + 1442695040888963407
    (rng & 0x7FFFFFFFFFFFFFFF) % n

run = (nv: int, np: int, mac: bool):
    ir = IrFn(nparams=np, vtypes=fill(i8(0), nv), code=fill(Ins(.nop), 100),
              slot_size=[i32(1), i32(8), i32(3), i32(4096)], slot_align=[i32(1), i32(8), i32(16), i32(64)])
    loop v in [0..nv): ir.vtypes[v] = i8(random(3))
    loop k in [0..nv): ir.args.push(i32(k))
    if nv > 0:
        ir.code[20] = Ins(.call, a=0, b=i32(nv))
        ir.code[30] = Ins(.callc, a=0, b=i32(nv), imm=5)
    backend_analyze(ir, layouts, false, false, false)
    call_pos = [0, 10, 20, 30, 50, 75, 99]
    loop v in [0..nv):
        first = random(50)
        if v < np: first = 0
        last = first + random(50)
        v_live[v] = IrUsePlan(first=first, last=last, nuse=random(4), ndef=1, weight=random(100))
        vloc[v] = LOC_SPILL
        if v >= np and v % 17 == 0: vloc[v] = LOC_CONST
        if v >= np and v % 19 == 0: vloc[v] = LOC_FCONST
        if v >= np and v % 23 == 0: vloc[v] = LOC_SLOT
        if v >= np and v % 29 == 0: vloc[v] = LOC_GLOBAL
        if v >= np and v % 31 == 0: v_live[v].last = -1
    before = ir
    previous_saved = a_saved
    a_allocate(ir)
    spill = [123]
    slots = [456]
    spill_snapshot = spill
    slot_snapshot = slots
    size = a_layout(ir, mac, spill, slots)
    assert(spill_snapshot == [123] and slot_snapshot == [456], "borrowed output replacement preserves snapshots")
    assert(ir.vtypes == before.vtypes and ir.args == before.args, "read-only IR")
    assert(size % 16 == 0 and a_out_size % 16 == 0 and a_scratch == a_out_size, "frame alignment")
    assert(a_save_off + 8 * a_saved.len() <= size, "callee saves fit")
    loop s in [0..slots.len()):
        assert(slots[s] % int(ir.slot_align[s]) == 0, "local alignment")
        assert(slots[s] + int(ir.slot_size[s]) <= a_save_off, "locals precede saves")
    loop v in [0..nv):
        print("{vloc[v]} {spill[v]}")
        if vloc[v] == LOC_SPILL:
            assert(spill[v] >= a_out_size + 16 and spill[v] % 8 == 0, "spill placement")
        loop u in [0..v):
            if v_live[v].last < 0 or v_live[u].last < 0: continue
            sv = a_live_start(np, v)
            su = a_live_start(np, u)
            if sv > v_live[u].last or su > v_live[v].last: continue
            if vloc[v] >= 0 and vloc[u] >= 0: assert(vloc[v] != vloc[u], "overlapping register allocation")
            if vloc[v] == LOC_SPILL and vloc[u] == LOC_SPILL: assert(spill[v] != spill[u], "overlapping spills")
    print("{size} {a_out_size} {a_save_off} {a_saved} {slots} {previous_saved}")

main = ():
    loop count in [0, 1, 7, 16, 32, 64, 128, 257, 4, 0, 90]:
        loop params in [0, 1, 8, 17, 32]:
            if params > count: continue
            loop mac in [false, true]: run(count, params, mac)
    # Inclusive calls forbid argument registers; strict crossings require saves.
    call_pos = [0, 10, 20]
    loop s in [-1, 0, 1, 9, 10, 11, 19, 20, 21]:
        loop e in [s, s + 1, s + 10]:
            inclusive = false
            strict = false
            loop p in call_pos:
                if p >= s and p <= e: inclusive = true
                if p > s and p < e: strict = true
            assert(a_call_in(s, e) == inclusive and a_crosses_call(s, e) == strict, "call endpoints")
    # Canonical integer constants still consume integer ABI argument positions.
    constant_call = IrFn(vtypes=fill(i8(0), 8) + fill(i8(3), 4), kval=fill(7, 12), args=[i32(0), i32(1), i32(2), i32(3), i32(4), i32(5), i32(6), i32(7), i32(8), i32(9), i32(10), i32(11)], code=[Ins(.call, a=0, b=12)])
    backend_analyze(constant_call, layouts, false, false, false)
    loop v in [0..12): vloc[v] = LOC_CONST
    a_saved = []
    spill: int[]
    slots: int[]
    frame = a_layout(constant_call, false, spill, slots)
    assert(a_out_size == 32 and frame == 48, "integer constants use x0-x7, then stack")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_arm64_allocate_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        stems = ('ir_types', 'ir_operands', 'backend_analysis', 'arm64_allocate')
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=30)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
