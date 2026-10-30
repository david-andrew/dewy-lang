"""Both native allocators and frame layout: frozen twin plus independent invariants."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
layouts = ir_operand_layouts()
rng = 716251
random = (n: int) -> int:
    rng = rng * 6364136223846793005 + 1442695040888963407
    (rng & 0x7FFFFFFFFFFFFFFF) % n

run = (nv: int, np: int, priority: bool, debug: bool, enabled: bool):
    ir = IrFn(name="sample", nparams=np, vtypes=fill(i8(0), nv), kval=fill(0, nv), code=fill(Ins(.nop), 100),
              slot_size=[i32(1), i32(8), i32(3), i32(4096)], slot_align=[i32(1), i32(8), i32(16), i32(64)])
    loop v in [0..nv): ir.vtypes[v] = i8(random(6))
    backend_analyze(ir, layouts, false, false, false, true)
    dbg_keep = fill(false, nv)
    call_pos = [0, 10, 20, 30, 50, 75, 99]
    call_w = [1, 1, 64, 1, 8, 1, 1]
    ir.code[20] = Ins(.call, c=2)
    loop p in call_pos:
        if p != 20: ir.code[p] = Ins(.call)
    loop pos in [0..101): v_start[pos] = -1
    loop v in [0..nv):
        first = random(50)
        if v < np: first = 0
        last = first + random(50)
        v_live[v] = IrUsePlan(first=first, last=last, nuse=1 + random(4), ndef=1, weight=1 + random(100))
        vloc[v] = LOC_SPILL
        vsave[v] = false
        dbg_keep[v] = debug and v % 3 == 0
        if v >= np and v % 17 == 0: vloc[v] = LOC_CONST
        if v >= np and v % 19 == 0: vloc[v] = LOC_FCONST
        if v >= np and v % 23 == 0: vloc[v] = LOC_SLOT
        if v >= np and v % 29 == 0: vloc[v] = LOC_GLOBAL
    v = nv
    loop v > 0:
        v -= 1
        if vloc[v] != LOC_SPILL: continue
        pos = v_live[v].first
        v_live[v].next_start = v_start[pos]
        v_start[pos] = v
    before = ir
    previous_spill = vspill
    ra_on = enabled
    ra_expire_visits = 0
    ra_spill_visits = 0
    ra_peak_gpr = 0
    ra_peak_xmm = 0
    x64_allocate(&ir, priority, debug, true)
    assert(ir.vtypes == before.vtypes and ir.code == before.code and ir.kval == before.kval, "read-only IR")
    assert(frame_size % 16 == 0 and vspill.len() == nv, "frame extent")
    loop s in [0..slot_off.len()):
        assert((-slot_off[s]) % int(ir.slot_align[s]) == 0 and -slot_off[s] <= frame_size, "local alignment")
    loop v in [0..nv):
        print("{vloc[v]} {vsave[v]} {vspill[v]}")
        if vloc[v] == LOC_SPILL or vsave[v]:
            assert(vspill[v] < 0 and -vspill[v] <= frame_size, "spill in frame")
        loop u in [0..v):
            if vloc[v] < 0 or vloc[u] < 0: continue
            if live_start(v) > v_live[u].last or live_start(u) > v_live[v].last: continue
            assert(vloc[v] != vloc[u], "live registers do not overlap")
        if not priority and not enabled:
            assert(vloc[v] < 0, "allocation disabled")
    print("{frame_size} {callee_off} {save_list} {slot_off} {previous_spill}")
    print("{ra_expire_visits} {ra_spill_visits} {ra_peak_gpr} {ra_peak_xmm}")

main = ():
    loop count in [0, 1, 7, 16, 32, 64, 128, 257, 4, 0, 90]:
        loop params in [0, 1, 8, 17]:
            if params > count: continue
            loop priority in [false, true]:
                loop debug in [false, true]:
                    loop enabled in [false, true]: run(count, params, priority, debug, enabled)
    # Real analysis supplies coalescing hints, canonical zero, cold calls and vectors.
    loop priority in [false, true]:
        ir = IrFn(name="hints", nparams=2, vtypes=[i8(0), i8(0), i8(3), i8(0), i8(0), i8(0)], kval=[0, 0, 0],
                  code=[Ins(.checked_sub, 0, 3, 2, 0, 0, 9), Ins(.add, 0, 4, 3, 1), Ins(.mov, 0, 5, 4), Ins(.ret, 0, -1, 5)])
        backend_analyze(ir, layouts, false, false, false, true)
        ra_on = true
        ra_dump = "hints"
        x64_allocate(&ir, priority, false, false)
        assert(vloc[2] == LOC_CONST and vloc[4] == vloc[5], "constant and dying-operand coalescing")
        loop v in [0..6): print(vloc[v])
        ra_dump = ""
    # Occupancy spans and mask endpoints, checked against a scalar bitmap.
    ra_words = 4
    loop lo in [0, 1, 63, 64, 65, 127]:
        loop hi in [lo, lo + 1, lo + 63]:
            ra_occ = fill(0, 32 * ra_words)
            ra_take(3, lo, hi)
            loop s in [0..192):
                loop len in [0, 1, 63]:
                    e = min(191, s + len)
                    assert(ra_free(3, s, e) == (e < lo or s > hi), "occupancy endpoints")
                    assert(ra_free(4, s, e), "other physical register")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_x64_allocate_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'ir_operands', 'backend_analysis', 'x64_encode', 'x64_allocate')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
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
        ran = subprocess.run([binary], capture_output=True, timeout=45)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append((ran.stdout, ran.stderr))
    assert outputs[0] == outputs[1]
    assert outputs[0][0].endswith(b'ok\n')
