"""Follow-up tests for Dewy generators v1:
- Top-level (global) `let g = lazy ...` iteration, `[g...]`, resume, and rejections
- `& no allocates` effect checking on fused vs unfused/allocating generator pipelines
- Combined-header fusion (`loop _ in [0..n) and v in gen()`) across native/wasm,
  default/release, leak checks, and x86_64 zero-alloc/zero-indirect-call objdump.

Covers compiler leaves: checker_generators, effect_scan, lower_generators, lower_group.
"""
import platform
import shutil
import subprocess

import pytest

from tests.support import build_case_batch, compiler  # noqa: F401


COMBINED_RUNTIME_CASES = {
    'combined_pipeline_and_bounds': '''
let pulls:int64 = 0
let defers:int64 = 0

gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }

counted_gen = (n:int64):>generator<int64> => lazy {
    defer { defers += 1 }
    loop i in [0..n) {
        pulls += 1
        i * 10
    }
}

main = ():>void => {
    # n = 0: zero pulls, zero defers (producer never entered!)
    pulls = 0
    defers = 0
    let sum0:int64 = 0
    loop _ in [0..0) and v in counted_gen(10) {
        sum0 += v
    }
    $runtime_assert (sum0 =? 0)
    $runtime_assert (pulls =? 0)
    $runtime_assert (defers =? 0)

    # n = 3: exact 3 pulls, 1 defer on exit (no 4th pull!)
    pulls = 0
    defers = 0
    let got3:array<int64> = []
    loop _ in [0..3) and v in counted_gen(10) {
        got3.push(v)
    }
    $runtime_assert (got3 =? [int64(0) int64(10) int64(20)])
    $runtime_assert (pulls =? 3)
    $runtime_assert (defers =? 1)

    # Pipeline with n < available
    let sum5:int64 = 0
    loop _ in [int64(0)..int64(5)) and v in gen_squares(gen_evens(gen_range(1000))) {
        sum5 += v
    }
    $runtime_assert (sum5 =? 0 + 4 + 16 + 36 + 64)

    # Pipeline with n > available (generator exhausts first)
    let sum_all:int64 = 0
    loop _ in [int64(0)..int64(100)) and v in gen_squares(gen_evens(gen_range(8))) {
        sum_all += v
    }
    $runtime_assert (sum_all =? 0 + 4 + 16 + 36)

    # Single-expression terminal yield (`yaux = 2`) with combined header
    let single_got:array<int64> = []
    loop i in [0..5) and v in lazy { int64(42) } {
        single_got.push(int64(i) * 100 + v)
    }
    $runtime_assert (single_got =? [int64(42)])
}
''',
    'combined_infinite_primes_and_multivalue_fib': '''
let prime_checks:int64 = 0

primes = ():>generator<int64> => lazy {
    let cand:int64 = 2
    loop true {
        let is_p = true
        let d:int64 = 2
        loop d * d <=? cand {
            if cand % d =? 0 {
                is_p = false
                break
            }
            d += 1
        }
        if is_p {
            prime_checks += 1
            cand
        }
        cand += 1
    }
}

fib = ():>generator<(int64 int64)> => lazy {
    let a:int64 = 0
    let b:int64 = 1
    let idx:int64 = 0
    loop true {
        (idx a)
        let next = a + b
        a = b
        b = next
        idx += 1
    }
}

main = ():>void => {
    prime_checks = 0
    let ps:array<int64> = []
    loop _ in [0..10) and p in primes() {
        ps.push(p)
    }
    $runtime_assert (ps =? [int64(2) int64(3) int64(5) int64(7) int64(11) int64(13) int64(17) int64(19) int64(23) int64(29)])
    # Must NOT pull an 11th prime after the 10th iteration!
    $runtime_assert (prime_checks =? 10)

    # Multivalue destructuring in combined header
    let fvals:array<int64> = []
    let fidx_sum:int64 = 0
    loop _ in [0..6) and (idx val) in fib() {
        fidx_sum += idx
        fvals.push(val)
    }
    $runtime_assert (fidx_sum =? 15)
    $runtime_assert (fvals =? [int64(0) int64(1) int64(1) int64(2) int64(3) int64(5)])
}
''',
    'combined_zip_arrays_gen_first_and_two_gens': '''
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_step10 = (n:int64):>generator<int64> => lazy loop i in [0..n) { i * 10 }

main = ():>void => {
    # Managed string array prefix + fused generator
    let labels = ["zero" "one" "two" "three"]
    let out:array<string> = []
    loop lbl in labels and v in gen_step10(10) {
        out.push("{lbl}:{v}")
    }
    $runtime_assert (out =? ["zero:0" "one:10" "two:20" "three:30"])

    # Generator-first combined header
    let gf:array<int64> = []
    loop v in gen_step10(10) and k in [int64(1)..int64(4)) {
        gf.push(v + k)
    }
    $runtime_assert (gf =? [int64(1) int64(12) int64(23)])

    # Two generators zipped (first fuses, second runs on frame)
    let zipped:array<int64> = []
    loop a in gen_range(4) and b in gen_step10(3) {
        zipped.push(a + b)
    }
    $runtime_assert (zipped =? [int64(0) int64(11) int64(22)])
}
''',
    'combined_control_flow_and_else': '''
let log:array<string> = []

gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }

logged_gen = (n:int64):>generator<int64> => lazy {
    defer { log.push("done") }
    loop i in [0..n) {
        log.push("y:{i}")
        i * 10
    }
}

early_ret = (n:int64):>int64 => {
    loop i in [int64(0)..n) and v in logged_gen(10) {
        if i =? 2 { return v + i }
    }
    -1
}

main = ():>void => {
    # continue and break inside combined fused loop
    log.clear()
    let got:array<int64> = []
    loop i in [int64(0)..int64(6)) and v in logged_gen(10) {
        if i =? 1 { continue }
        got.push(v)
        if i =? 3 { break }
    }
    $runtime_assert (got =? [int64(0) int64(20) int64(30)])
    $runtime_assert (log =? ["y:0" "y:1" "y:2" "y:3" "done"])

    # early return unwinds producer defer
    log.clear()
    $runtime_assert (early_ret(5) =? 22)
    $runtime_assert (log =? ["y:0" "y:1" "y:2" "done"])

    # labeled break/continue from combined fused loop to enclosing loop
    let hits:array<int64> = []
    $outer
    loop a in [int64(0)..int64(4)) {
        loop _ in [int64(0)..int64(4)) and b in gen_range(10) {
            if a =? 1 and b =? 2 { continue $outer }
            if a =? 2 and b =? 1 { break $outer }
            hits.push(a * 10 + b)
        }
    }
    $runtime_assert (hits =? [int64(0) int64(1) int64(2) int64(3) int64(10) int64(11) int64(20)])

    # loop ... else on combined fused loop
    let hit_empty_range = false
    loop _ in [0..0) and v in gen_range(5) {
        let _ = v
    } else {
        hit_empty_range = true
    }
    $runtime_assert (hit_empty_range)

    let hit_empty_gen = false
    loop _ in [0..5) and v in gen_range(0) {
        let _ = v
    } else {
        hit_empty_gen = true
    }
    $runtime_assert (hit_empty_gen)

    let hit_nonempty = false
    let acc:int64 = 0
    loop _ in [0..3) and v in gen_range(5) {
        acc += v
    } else {
        hit_nonempty = true
    }
    $runtime_assert (acc =? 3 and not hit_nonempty)
}
''',
    'no_allocates_fused_pipelines': '''
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }

sum_inline = (n:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop v in lazy loop i in [0..n) { i } {
        total += v
    }
    total
}

sum_local_captured = (n:int64):>int64 & no allocates => {
    let limit = n
    let src = lazy loop i in [0..limit) { i }
    let evens = lazy loop x in src { if x % 2 =? 0 { x } }
    let sq:generator<int64> = lazy loop y in evens { y * y }
    let total:int64 = 0
    loop v in sq { total += v }
    total
}

sum_factory_chain = (n:int64):>int64 & no allocates & no panics => {
    let total:int64 = 0
    loop v in gen_squares(gen_evens(gen_range(n))) {
        total += v
    }
    total
}

sum_combined = (k:int64 n:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop _ in [int64(0)..k) and v in gen_squares(gen_evens(gen_range(n))) {
        total += v
    }
    total
}

sum_repeated_factories = (a:int64 b:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop x in gen_range(a) { total += x }
    loop y in gen_evens(gen_range(b)) { total += y }
    total
}

sum_param_array = (xs:array<int64>):>int64 & no allocates => {
    let total:int64 = 0
    loop v in lazy loop x in xs { x } {
        total += v
    }
    let g:generator<int64> = lazy loop x in xs { x * 2 }
    loop v in g {
        total += v
    }
    total
}

primes_noalloc = ():>generator<int64> => lazy {
    let cand:int64 = 2
    loop true {
        let is_p = true
        let d:int64 = 2
        loop d * d <=? cand {
            if cand % d =? 0 { is_p = false; break }
            d += 1
        }
        if is_p { cand }
        cand += 1
    }
}

sum_primes_10 = ():>int64 & no allocates => {
    let total:int64 = 0
    loop _ in [int64(0)..int64(10)) and p in primes_noalloc() {
        total += p
    }
    total
}

main = ():>void => {
    $runtime_assert (sum_inline(5) =? 10)
    $runtime_assert (sum_local_captured(20) =? 1140)
    $runtime_assert (sum_factory_chain(20) =? 1140)
    $runtime_assert (sum_combined(5 100) =? 120)
    $runtime_assert (sum_repeated_factories(5 6) =? 10 + 6)
    $runtime_assert (sum_param_array([int64(3) int64(4) int64(5)]) =? 36)
    $runtime_assert (sum_primes_10() =? 129)
}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generators_followup_runtime(compiler, tmp_path, target, release):
    body = [f'case_{i}()' for i in range(len(COMBINED_RUNTIME_CASES))]
    cmd, err = build_case_batch(compiler, tmp_path, COMBINED_RUNTIME_CASES, body, release, target)
    assert cmd is not None, err
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generators_toplevel_global(compiler, tmp_path, target, release):
    """Top-level `let g = lazy ...` works in `[g...]`, `loop x in g`, combined loops,
    resume across loops/functions, and struct fields containing generators."""
    src = tmp_path / 'toplevel_gen.dewy'
    src.write_text('''$runtime_checks
Holder:type = [g:generator<int>]

let g1 = lazy (1 2 3)
let a1 = [g1...]
$runtime_assert (a1 =? [1 2 3])
$runtime_assert ([g1...] =? [])

let g2 = lazy (10 20 30 40)
let first = 0
loop x in g2 {
    first = x
    break
}
$runtime_assert (first =? 10)
$runtime_assert ([g2...] =? [20 30 40])

let g3 = lazy (100 200 300 400)
let head3:array<int> = []
loop _ in [0..2) and x in g3 {
    head3.push(x)
}
$runtime_assert (head3 =? [100 200])
$runtime_assert ([g3...] =? [300 400])

let g4 = lazy loop i in [1..6) { i * 10 }

pull_two = ():>array<int> => {
    let out:array<int> = []
    loop _ in [0..2) and x in g4 {
        out.push(x)
    }
    out
}

let h = Holder[g=lazy (7 8 9)]
$runtime_assert ([h.g...] =? [7 8 9])

$runtime_assert (pull_two() =? [10 20])
$runtime_assert ([g4...] =? [30 40 50])
''')
    out = tmp_path / 'toplevel_gen'
    args = [compiler, 'build', src, '-o', out]
    if release:
        args.append('--release')
    if target == 'wasm':
        args += ['--target', 'wasm32']
    res = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stdout + res.stderr
    if target == 'wasm':
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed to execute the generated web runner')
        from tests.support import Scripts
        scripts = Scripts()
        scripts.feed(out.with_suffix('.html').read_text())
        runner = tmp_path / 'toplevel_gen.cjs'
        runner.write_text('\n'.join(scripts.parts))
        cmd = [node, str(runner)]
    else:
        cmd = [str(out)]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.core_quick
def test_generators_combined_managed_no_leak(compiler, tmp_path):
    """Combined-header fusion with managed string prefix locals & yielded strings leaks nothing."""
    src = tmp_path / 'comb_leak.dewy'
    exe = tmp_path / 'comb_leak'
    src.write_text('''$runtime_checks
make_items = (n:int64):>generator<string> => lazy loop i in [0..n) {
    "val:{i}"
}

exercise = ():>int64 => {
    let labels = ["a0" "b1" "c2" "d3" "e4"]
    let total:int64 = 0
    # Normal completion (prefix exhausts first)
    loop lbl in labels and s in make_items(10) {
        total += lbl.length + s.length
    }
    # Early break inside consumer
    loop lbl in labels and s in make_items(10) {
        total += lbl.length + s.length
        if lbl =? "b1" { break }
    }
    # Generator exhausts first
    loop lbl in labels and s in make_items(2) {
        total += lbl.length + s.length
    }
    # Empty prefix (zero pulls)
    let empty:array<string> = []
    loop lbl in empty and s in make_items(5) {
        total += lbl.length + s.length
    }
    total
}

main = ():>void => {
    let r0 = exercise()
    let before = alloc_count()
    loop _ in [0..30) {
        let r = exercise()
        $runtime_assert (r =? r0)
    }
    $runtime_assert (alloc_count() =? before)
}
''')
    res = subprocess.run([compiler, 'build', src, '-o', exe], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stdout + res.stderr
    run = subprocess.run([exe], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.core_quick
def test_generators_combined_fusion_zero_alloc_and_direct(compiler, tmp_path):
    """Verify combined-header fused generator pipelines emit zero heap allocation
    and zero indirect step-function dispatch in release native code."""
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64') or not shutil.which('objdump'):
        pytest.skip('x86_64 Linux objdump check')
    programs = {
        'combined_pipe': '''$runtime_checks
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
gen_squares = (g:generator<int64>):>generator<int64> => lazy loop y in g { y * y }
main = ():>void => {
    let n:int64 = 1000
    let k:int64 = 200
    let total:int64 = 0
    loop _ in [int64(0)..k) and v in gen_squares(gen_evens(gen_range(n))) {
        total += v
    }
    $runtime_assert (total =? 10586800)
}
''',
        'combined_primes': '''$runtime_checks
primes = ():>generator<int64> => lazy {
    let cand:int64 = 2
    loop true {
        let is_p = true
        let d:int64 = 2
        loop d * d <=? cand {
            if cand % d =? 0 {
                is_p = false
                break
            }
            d += 1
        }
        if is_p { cand }
        cand += 1
    }
}
main = ():>void => {
    let total:int64 = 0
    loop _ in [int64(0)..int64(10)) and p in primes() {
        total += p
    }
    $runtime_assert (total =? 129)
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


REJECT_CASES = [
    ('global_copy', '''
let g = lazy (1 2 3)
let g2 = g
let _ = [g2...]
''', 'cannot copy a generator'),
    ('global_reentry_loop', '''
let g = lazy (1 2 3)
loop _ in g {
    loop _ in g {}
}
''', 'while iterating over it'),
    ('global_reentry_collect', '''
let g = lazy (1 2 3)
loop _ in g {
    let _ = [g...]
}
''', 'while iterating over it'),
    ('global_reentry_combined', '''
let g = lazy (1 2 3)
loop a in g and b in g {
    let _ = a + b
}
''', 'twice in the same loop'),
    ('no_allocates_producer_allocs', '''
alloc_gen = (n:int64):>generator<int64> => lazy loop i in [0..n) {
    let xs = [i]
    xs.length
}
f = (n:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop v in alloc_gen(n) { total += v }
    total
}
main = ():>void => { let _ = f(5) }
''', 'allocates'),
    ('no_allocates_unfused_multiuse', '''
f = ():>int64 & no allocates => {
    let g = lazy (int64(1) int64(2) int64(3))
    let total:int64 = 0
    loop v in g { total += v; break }
    loop v in g { total += v }
    total
}
main = ():>void => { let _ = f() }
''', 'allocates'),
    ('no_allocates_recursive_delegation', '''
rec_gen = (n:int64):>generator<int64> => lazy {
    if n >? 0 {
        n
        rec_gen(n - 1)...
    }
}
f = (n:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop v in rec_gen(n) { total += v }
    total
}
main = ():>void => { let _ = f(3) }
''', 'allocates'),
    ('no_allocates_opaque_param', '''
f = (g:generator<int64>):>int64 & no allocates => {
    let total:int64 = 0
    loop v in g { total += v }
    total
}
main = ():>void => { let _ = f(lazy (int64(1))) }
''', 'allocates'),
    ('no_allocates_second_call_allocs', '''
gen_range = (n:int64):>generator<int64> => lazy loop i in [0..n) { i }
gen_evens = (g:generator<int64>):>generator<int64> => lazy loop x in g { if x % 2 =? 0 { x } }
alloc_gen = (n:int64):>generator<int64> => lazy loop i in [0..n) {
    let xs = [i]
    xs.length
}
f = (n:int64):>int64 & no allocates => {
    let total:int64 = 0
    loop v in gen_evens(gen_range(n)) { total += v }
    loop v in gen_evens(alloc_gen(n)) { total += v }
    total
}
main = ():>void => { let _ = f(5) }
''', 'allocates'),
]


@pytest.mark.core_quick
@pytest.mark.parametrize('name,source,expected', REJECT_CASES, ids=[c[0] for c in REJECT_CASES])
def test_generators_followup_rejections(compiler, tmp_path, name, source, expected):
    src = tmp_path / f'{name}.dewy'
    out = tmp_path / name
    src.write_text('$runtime_checks\n' + source)
    res = subprocess.run([compiler, 'build', src, '-o', out], capture_output=True, text=True, timeout=30)
    assert res.returncode != 0, f'expected compile failure for {name}'
    combined = (res.stdout + res.stderr).lower()
    assert expected.lower() in combined, f'expected {expected!r} in:\n{res.stdout}{res.stderr}'
