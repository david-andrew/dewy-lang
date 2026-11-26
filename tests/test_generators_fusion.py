"""Local loop fusion tests for Dewy generators v1: semantic equivalence across
native/web/default/release and zero-allocation/zero-indirect-call verification.

Covers compiler leaves: lower_generators, lower_group, lower_functions.
"""
import platform
import shutil
import subprocess

import pytest

from tests.support import build_case_batch, compiler  # noqa: F401


RUNTIME_CASES = {
    'local_and_factory_pipelines': '''
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }
gen_take = (limit:int64 g:generator<int64>):>generator<int64> => lazy {
    let k:int64 = 0
    loop x in g {
        if k >=? limit { break }
        k += 1
        x
    }
}

main = ():>void => {
    # Chained local variables
    let src = lazy loop i in [0..20) { i }
    let evens = lazy loop x in src { if x % 2 =? 0 { x } }
    let sq:generator<int64> = lazy loop y in evens { y * y }
    let total:int64 = 0
    loop v in sq { total += v }
    $runtime_assert (total =? 1140)

    # Chained factory calls + take
    let sum2:int64 = 0
    loop v in gen_take(5 gen_squares(gen_evens(gen_range(100)))) {
        sum2 += v
    }
    $runtime_assert (sum2 =? 0 + 4 + 16 + 36 + 64)

    # Collect [lazy ...]
    let collected = [gen_squares(gen_evens(gen_range(8)))...]
    $runtime_assert (collected =? [int64(0) int64(4) int64(16) int64(36)])
}
''',
    'capture_order_and_mutation': '''
main = ():>void => {
    let k:int64 = 10
    let g:generator<int64> = lazy loop i in [0..3) { i + k }
    k = 99
    let xs = [g...]
    $runtime_assert (xs =? [int64(10) int64(11) int64(12)])
}
''',
    'break_continue_labels_and_defer': '''
let log:array<string> = []

gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }

with_defer = (n:int64):>generator<int64> => lazy {
    defer { log.push("outer_end") }
    loop i in [0..n) {
        defer { log.push("i:{i}") }
        if i =? 1 { continue }
        i * 10
    }
}

labeled_gen = ():>generator<int64> => $done lazy {
    defer { log.push("done_defer") }
    int64(1)
    int64(2)
    break $done
    int64(3)
}

main = ():>void => {
    # Consumer continue & break with producer defer LIFO unwind
    log.clear()
    let got:array<int64> = []
    loop v in with_defer(10) {
        if v =? 20 { continue }
        got.push(v)
        if v =? 30 { break }
    }
    $runtime_assert (got =? [int64(0) int64(30)])
    $runtime_assert (log =? ["i:0" "i:1" "i:2" "i:3" "outer_end"])

    # Labeled break inside fused generator
    log.clear()
    $runtime_assert ([labeled_gen()...] =? [int64(1) int64(2)])
    $runtime_assert (log =? ["done_defer"])

    # Labeled break/continue from fused consumer to enclosing outer loop
    let hits:array<int64> = []
    $outer
    loop a in [0..4) {
        loop b in gen_range(5) {
            if a =? 1 and b =? 2 { continue $outer }
            if a =? 2 and b =? 1 { break $outer }
            hits.push(a * 10 + b)
        }
    }
    $runtime_assert (hits =? [int64(0) int64(1) int64(2) int64(3) int64(4) int64(10) int64(11) int64(20)])

    # Nested fused loops calling the SAME factory
    let pairs:int64 = 0
    loop a in gen_range(4) {
        loop b in gen_range(3) {
            pairs += a + b
        }
    }
    $runtime_assert (pairs =? 30)
}
''',
    'else_indexed_early_return_and_managed': '''
let events:array<string> = []

gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }

find_over = (n:int64 threshold:int64):>int64 => {
    let src = lazy {
        defer { events.push("find_done") }
        loop i in [0..n) { i }
    }
    loop v in gen_squares(gen_evens(src)) {
        if v >? threshold { return v }
    }
    -1
}

main = ():>void => {
    # Loop else: runs when fused generator yields 0 items, skipped otherwise
    let empty_hit = false
    let empty_count:int64 = 0
    loop _ in gen_range(0) {
        empty_count += 1
    } else {
        empty_hit = true
    }
    $runtime_assert (empty_count =? 0 and empty_hit)

    let nonempty_hit = false
    let count:int64 = 0
    loop _ in gen_range(3) {
        count += 1
    } else {
        nonempty_hit = true
    }
    $runtime_assert (count =? 3 and not nonempty_hit)

    # Indexed loop over filtered fused pipeline
    let idxs:array<int> = []
    let vals:array<int64> = []
    loop idx in 0.. and v in gen_evens(gen_range(7)) {
        idxs.push(idx)
        vals.push(v)
    }
    $runtime_assert (idxs =? [0 1 2 3])
    $runtime_assert (vals =? [int64(0) int64(2) int64(4) int64(6)])

    # Early return unwinds producer defer cleanly
    events.clear()
    $runtime_assert (find_over(20 50) =? 64)
    $runtime_assert (events =? ["find_done"])

    # Managed strings + aggregate tuple elements through fused pipeline
    let words = ["a" "bb" "ccc" "dddd"]
    let long_words = lazy loop w in words {
        if w.length >=? 3 { w }
    }
    $runtime_assert ([long_words...] =? ["ccc" "dddd"])

    let pairs_gen:generator<(int int)> = lazy loop i in [1..4) { (i i * 10) }
    let psum = 0
    loop (a b) in pairs_gen { psum += a + b }
    $runtime_assert (psum =? 66)
}
''',
    'fused_or_throw_and_fallback': '''
ReadFailed:type = type of error & [code:int]

step = (i:int):>int | ReadFailed => {
    if i =? 2 { return ReadFailed[code=7] }
    i * 10
}

main = ():>void => {
    # Fused generator with or_throw failure yield
    let got:array<int> = []
    let code = -1
    loop item in lazy {
        loop i in [0..5) {
            let v = step(i) or_throw
            v
        }
    } {
        match item {
            e:ReadFailed => { code = e.code }
            v:int => { got.push(v) }
        }
    }
    $runtime_assert (got =? [0 10])
    $runtime_assert (code =? 7)

    # Multi-use named generator must NOT fuse (resumes after break!)
    let g = lazy (10 20 30)
    loop x in g {
        $runtime_assert (x =? 10)
        break
    }
    $runtime_assert ([g...] =? [20 30])
}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generators_fusion_runtime(compiler, tmp_path, target, release):
    body = [f'case_{i}()' for i in range(len(RUNTIME_CASES))]
    cmd, err = build_case_batch(compiler, tmp_path, RUNTIME_CASES, body, release, target)
    assert cmd is not None, err
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.core_quick
def test_generators_fusion_zero_alloc_and_direct(compiler, tmp_path):
    """Verify fused local & factory generator pipelines emit zero heap allocation
    and zero indirect step-function dispatch in release native code."""
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64') or not shutil.which('objdump'):
        pytest.skip('x86_64 Linux objdump check')
    programs = {
        'local_pipe': '''$runtime_checks
main = ():>void => {
    let n:int64 = 1000
    let src = lazy loop i in [0..n) { i }
    let evens = lazy loop x in src { if x % 2 =? 0 { x } }
    let sq:generator<int64> = lazy loop y in evens { y * y }
    let total:int64 = 0
    loop v in sq { total += v }
    $runtime_assert (total =? 166167000)
}
''',
        'factory_pipe': '''$runtime_checks
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }
main = ():>void => {
    let n:int64 = 1000
    let total:int64 = 0
    loop v in gen_squares(gen_evens(gen_range(n))) { total += v }
    $runtime_assert (total =? 166167000)
}
''',
    }
    for name, code in programs.items():
        src = tmp_path / f'{name}.dewy'
        exe = tmp_path / name
        src.write_text(code)
        res = subprocess.run([compiler, 'build', '--release', src, '-o', exe], capture_output=True, text=True, timeout=30)
        assert res.returncode == 0, res.stdout + res.stderr
        run = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stdout + run.stderr
        dis = subprocess.run(['objdump', '-d', exe], capture_output=True, text=True, check=True).stdout
        main_dis = dis.split('<main>:')[1].split('\n\n')[0]
        assert '__alloc' not in main_dis, f'{name} allocated in main:\n{main_dis}'
        assert 'call   *' not in main_dis, f'{name} used indirect call in main:\n{main_dis}'
        assert '__h_gen_step' not in main_dis, f'{name} called state-machine step helper in main:\n{main_dis}'
