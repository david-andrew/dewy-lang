"""Driver execution ownership: exact pass traces, snapshots and graph policies."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
ir = IrFn()
kc_fn = 0
rel_fns: IrFn[]
rel_by_index: int[]
lower_only = false
opt_release = false
dbg_on = false
watch_build = false
repl_image = false
host_ir = false
dump = false
target_wasm = false
target_arm64 = false
fz_ready = false
events: int[]
parallel_ok = false
reenter = false
clock_value = 0.0
make_fn = (n: int) -> IrFn:
    f = IrFn()
    f.fn_index = n
    f.ret = -1
    f
optimize = ():
    events.push(1)
    ir.kval.push(1)
fast_inline_into = (): events.push(2)
fast_vectorize = (): events.push(3)
loop_versioning = (): events.push(4)
o_licm = (code: Ins[]) -> Ins[]:
    events.push(5)
    code
host_dump = (): events.push(6)
plain_dump = (): events.push(7)
wasm = (): events.push(8)
arm64 = (): events.push(9)
x64 = ():
    events.push(10)
    if reenter:
        emit_queue.push(make_fn(99))
        emit_queue_rel.push(false)
inlinable = (f: IrFn) -> int:
    events.push(100 + f.fn_index)
    f.kval.len()
inline_into = (k: int, fs: IrFn[], can: int[]) -> bool:
    events.push(200 + k)
    assert(ir.fn_index == fs[k].fn_index, "active inline function")
    assert(can[k] == fs[k].kval.len(), "inlinability follows snapshot")
    if k % 2 != 0: return false
    ir.kval.push(2)
    true
prepare = (fs: IrFn[]): events.push(300 + fs.len())
parallel = (fs: IrFn[], fin: bool[]) -> bool:
    events.push(400 + fs.len())
    assert(fin.len() == fs.len(), "parallel flags")
    parallel_ok
fused = (fs: IrFn[]):
    events.push(500 + fs.len())
    assert(not fz_ready and not queue_emit and emit_queue.len() == 0, "fused queue ownership")
phase = (p: int) -> int:
    events.push(600 + p)
    12
lf_phase = (p: int, lf: int) -> int:
    events.push(700 + lf)
    assert(p == 7, "emit phase")
    13
restore = (b: int): events.push(800 + b)
clock = () -> f64:
    clock_value += 1.0
    clock_value
release_timing = (a: f64, b: f64, c: f64):
    assert(a < b and b < c, "release timing order")
    events.push(900)
emit_timing = (a: f64): events.push(901)
context = DriverState(&ir, &kc_fn, &rel_fns, &rel_by_index, &lower_only, &opt_release, &dbg_on, &watch_build, &repl_image, &host_ir, &dump, &target_wasm, &target_arm64, &fz_ready)
host = DriverHost(optimize, fast_inline_into, fast_vectorize, loop_versioning, o_licm, host_dump, plain_dump, wasm, arm64, x64, inlinable, inline_into, prepare, parallel, fused, phase, lf_phase, restore, clock, release_timing, emit_timing)
bound = driver_bind(&context, &host)
reset = ():
    ir = make_fn(0)
    kc_fn = 0
    rel_fns = []
    rel_by_index = []
    lower_only = false
    opt_release = false
    dbg_on = false
    watch_build = false
    repl_image = false
    host_ir = false
    dump = false
    target_wasm = false
    target_arm64 = false
    fz_ready = false
    events = []
    parallel_ok = false
    reenter = false
    emit_queue = []
    emit_queue_rel = []
    queue_emit = false

main = ():
    # Independent oracle over every combination of dispatch and optimization policy.
    loop mask in [0..512):
        reset()
        opt_release = (mask & 1) != 0
        dbg_on = (mask & 2) != 0
        watch_build = (mask & 4) != 0
        repl_image = (mask & 8) != 0
        host_ir = (mask & 16) != 0
        dump = (mask & 32) != 0
        target_wasm = (mask & 64) != 0
        target_arm64 = (mask & 128) != 0
        finish = (mask & 256) != 0
        expected = [606]
        if finish:
            expected.push(4)
            expected.push(5)
        else if not opt_release and not dbg_on:
            if not watch_build and not repl_image: expected.push(2)
            expected.push(1)
            if not watch_build and not repl_image: expected.push(3)
        expected.push(812)
        if host_ir: expected.push(6)
        else:
            if dump: expected.push(7)
            expected.push(if target_wasm: 8 else if target_arm64: 9 else: 10)
        emit_now(finish)
        assert(events == expected, "pass order and backend policy")
        assert(kc_fn == (if finish or (not opt_release and not dbg_on): 1 else: 0), "function counter")
        print(events)
    reset()
    lower_only = true
    queue_emit = true
    emit_function()
    assert(emit_queue.len() == 0 and events.len() == 0, "lower-only bypass")
    lower_only = false
    ir = make_fn(5)
    emit_function()
    ir.kval.push(9)
    assert(emit_queue[0].kval.len() == 0 and emit_queue_rel == [false], "queued value snapshot")
    # Cycles, cold calls and out-of-map calls: only ordinary direct callees order.
    reset()
    fs = [make_fn(0), make_fn(1), make_fn(2), make_fn(3)]
    fs[0].code = [Ins(.call, 0, 0, 0, 0, 0, 1), Ins(.call, 0, 0, 0, 0, 1, 3), Ins(.call, 0, 0, 0, 0, 0, 99)]
    fs[1].code = [Ins(.call, 0, 0, 0, 0, 0, 2)]
    fs[2].code = [Ins(.call, 0, 0, 0, 0, 0, 1)]
    rel_by_index = [0, 1, 2, 3]
    assert(callee_order(fs) == [2, 1, 0, 3], "callee DFS cycle order")
    # Release snapshots survive optimization and queue publication.
    loop queued in [false, true]:
        reset()
        opt_release = true
        queue_emit = queued
        rel_fns = fs
        rel_by_index = [0, 1, 2, 3]
        old = rel_fns
        release_pipeline()
        assert(rel_fns.len() == 0 and old[0].kval.len() == 0, "release snapshot and clear")
        assert(kc_fn == (if queued: 8 else: 12), "release function counters")
        if queued:
            assert(emit_queue_rel == [true, true, true, true], "deferred finishing")
            assert(emit_queue[0].kval == [1, 2, 1] and emit_queue[1].kval == [1], "inline snapshot update")
        print(events)
    # Reachability keeps exports, checked helpers and address-taken functions.
    reset()
    loop n in [5, 1, 7, 2, 9, 4]: emit_queue.push(make_fn(n))
    emit_queue[0].code = [Ins(.call, 0, 0, 0, 0, 0, 1)]
    emit_queue[1].code = [Ins(.faddr, 0, 0, 0, 0, 0, 7)]
    emit_queue[2].code = [Ins(.checked_mul, 0, 0, 0, 0, 0, 2)]
    emit_queue[4].export_name = "entry"
    emit_queue_rel = [true, false, true, false, true, false]
    old = emit_queue
    roots = [5, -1, 3]
    prune_emit_queue(roots, 10)
    assert(emit_queue.len() == 5 and old.len() == 6 and roots == [5, -1, 3], "prune snapshots")
    assert(emit_queue_rel == [true, false, true, false, true], "compacted flags")
    loop i in [0..5): assert(emit_queue[i].fn_index == old[i].fn_index, "stable live order")
    # Fast/fused/parallel/host-IR paths and additions during serial callbacks.
    loop mask in [0..32):
        reset()
        fz_ready = (mask & 1) != 0
        parallel_ok = (mask & 2) != 0
        host_ir = (mask & 4) != 0
        dbg_on = (mask & 8) != 0
        opt_release = (mask & 16) != 0
        emit_queue = [make_fn(1), make_fn(2)]
        emit_queue_rel = [false, true]
        queue_emit = true
        reenter = true
        emit_queued()
        assert(not queue_emit and not fz_ready, "queue detached before dispatch")
        if (mask & 1) != 0: assert(events == [502], "fused shortcut")
        else if parallel_ok and not host_ir: assert(events[events.len() - 1] == 402, "parallel shortcut")
        else:
            assert(events[events.len() - 1] == 901, "serial completion")
            assert(emit_queue.len() == (if host_ir: 0 else: 2), "reentrant queued work survives")
        print(events)
    reset()
    emit_queued()
    assert(events == [300, 400, 901], "empty queue services")
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_driver_pipeline_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('ir_types', 'opt_returns', 'driver_pipeline')
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
        ran = subprocess.run([binary], capture_output=True, timeout=30)
        assert ran.returncode == 0, ran.stdout[-2000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
