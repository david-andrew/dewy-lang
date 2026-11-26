"""Core Dewy generators v1 behavior: lazy evaluation, pulling, multivalues, labels,
fresh spreads, and undecided-feature rejections across native and web targets.

Covers compiler leaves: checker_generators, lower_generators, checks_index_hooks,
missing_member_checks, dewy_reader, dewy_reader_state, dewy_fast_lex, dewy_lexer,
dewy_frontend, dewy_file, checker_load_module, checker_loop_bindings,
checker_type_names, checker_resolve, coercion_queries, coerce_expression,
type_constructors, type_format, type_layout, type_match, type_ops, type_properties,
type_substitute, checker_types, dwarf_format, pdb_format, lower_storage,
lower_analysis, panic_inventory, isolation_ops, ownership_checks.
"""
import subprocess

import pytest

from tests.support import build_case_batch, compiler  # noqa: F401


RUNTIME_CASES = {
    'basic_flatten': '''
main = ():>void => {
    let xs = [lazy (1 (2 3) 4)...]
$runtime_assert (xs =? [1 2 3 4])
    let empty:array<int> = [lazy ()...]
$runtime_assert (empty.length =? 0)
    let single = [lazy 42...]
$runtime_assert (single =? [42])
    let blk = [lazy { let a = 5; a + 1; a + 2 }...]
$runtime_assert (blk =? [7])
    let blk2 = [lazy { let a = 5; a + 1 a + 2 }...]
$runtime_assert (blk2 =? [6 7])
}
''',
    'lazy_until_pulled': '''
let trace:array<string> = []

make = ():>generator<int> => lazy {
    trace.push("start")
    10
    trace.push("mid")
    20
    trace.push("end")
}

main = ():>void => {
    let g = make()
$runtime_assert (trace.length =? 0)
    let got:array<int> = []
    loop x in g {
        got.push(x)
        break
    }
$runtime_assert (got =? [10])
$runtime_assert (trace =? ["start"])
    let rest = [g...]
$runtime_assert (rest =? [20])
$runtime_assert (trace =? ["start" "mid" "end"])
    let after = [g...]
$runtime_assert (after.length =? 0)
}
''',
    'multivalue_fib': '''
fib = ():>generator<(int int)> => lazy {
    let a = 0
    let b = 1
    loop true {
        (a b)
        let next = a + b
        a = b
        b = next
    }
}

pairs = ():>generator<(int int)> => lazy ((1 2) (3 4) (5 6))

main = ():>void => {
    let first6:array<int> = []
    loop _ in [0..6) and (a b) in fib() {
        first6.push(a)
    }
$runtime_assert (first6 =? [0 1 1 2 3 5])
    let sums:array<int> = []
    loop (x y) in pairs() {
        sums.push(x * 10 + y)
    }
$runtime_assert (sums =? [12 34 56])
}
''',
    'infinite_primes_and_squares': '''
squares = ():>generator<int> => lazy loop i in 0.. i * i

primes = ():>generator<int> => $outer lazy loop n in 2.. {
    loop d in 2.. {
        if d * d >? n { break }
        if n % d =? 0 { continue $outer }
    }
    n
}

main = ():>void => {
    let sq = squares()
    let a:array<int> = []
    loop _ in [0..4) and s in sq { a.push(s) }
$runtime_assert (a =? [0 1 4 9])
    let b:array<int> = []
    loop _ in [0..3) and s in sq { b.push(s) }
$runtime_assert (b =? [16 25 36])

    let ps:array<int> = []
    loop _ in [0..10) and p in primes() { ps.push(p) }
$runtime_assert (ps =? [2 3 5 7 11 13 17 19 23 29])
}
''',
    'labeled_lazy_break': '''
main = ():>void => {
    let g = $done lazy {
        1
        if true {
            2
            break $done
        }
        3
    }
$runtime_assert ([g...] =? [1 2])

    let g2 = $stop lazy {
        loop i in [0..10) {
            if i =? 4 { break $stop }
            i
        }
        99
    }
$runtime_assert ([g2...] =? [0 1 2 3])
}
''',
    'control_flow_and_else': '''
classify = (xs:array<int>):>generator<string> => lazy {
    loop x in xs {
        match x {
            <0> => "zero"
            <1> => { "one" "uno" }
            _ => if x >? 0 { "pos" } else { "neg" }
        }
    }
}

main = ():>void => {
$runtime_assert ([classify([0 1 5 -2])...] =? ["zero" "one" "uno" "pos" "neg"])
    let fell = false
    let bad = false
    loop _ in lazy () {
        bad = true
    } else {
        fell = true
    }
    $runtime_assert (fell and not bad)
    let ran = false
    let bad2 = false
    loop x in lazy (7) {
        $runtime_assert (x =? 7)
        ran = true
    } else {
        bad2 = true
    }
    $runtime_assert (ran and not bad2)
}
''',
    'zip_and_indexed_loops': '''
main = ():>void => {
    let g1 = lazy (1 2 3 4)
    let g2 = lazy (10 20)
    let zipped:array<int> = []
    loop a in g1 and b in g2 { zipped.push(a + b) }
$runtime_assert (zipped =? [11 22])

    let idx_out:array<int> = []
    loop i in 0.. and v in lazy (100 200 300) {
        idx_out.push(i * 1000 + v)
    }
$runtime_assert (idx_out =? [100 1200 2300])
}
''',
    'one_token_read_and_fresh_spread': '''
add = (a:int b:int):>int => a + b

first_item = (g:generator<int>):>int? => {
    loop x in g { return x }
    none
}

main = ():>void => {
$runtime_assert (first_item(lazy (77 88 99)) =? 77)
$runtime_assert (first_item(lazy ()) =? none)
$runtime_assert (add(lazy (20 22)...) =? 42)
    let g = lazy (100 23)
$runtime_assert (add(g...) =? 123)
}
''',
    'captures_and_strings': '''
scale_from = (base:int factor:int n:int):>generator<int> => lazy {
    loop i in [0..n) {
        (base + i) * factor
    }
}

words = (prefix:string):>generator<string> => lazy {
    "{prefix}-a"
    "{prefix}-b"
}

main = ():>void => {
$runtime_assert ([scale_from(10 2 4)...] =? [20 22 24 26])
$runtime_assert ([words("hi")...] =? ["hi-a" "hi-b"])
}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generators_core_runtime(compiler, tmp_path, target, release):
    body = [f'case_{i}()' for i in range(len(RUNTIME_CASES))]
    cmd, err = build_case_batch(compiler, tmp_path, RUNTIME_CASES, body, release, target)
    assert cmd is not None, err
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


REJECT_CASES = [
    ('g_next', '''
main = ():>void => {
    let g = lazy (1 2)
    let _ = g.next
}
''', 'not decided yet'),
    ('g_index', '''
main = ():>void => {
    let g = lazy (1 2)
    let _ = g[0]
}
''', 'not decided yet'),
    ('g_slice', '''
main = ():>void => {
    let g = lazy (1 2 3)
    let _ = g[0..2)
}
''', 'not decided yet'),
    ('type_length_attr', '''
f = (g:generator<int length=2>):>void => {}
main = ():>void => {}
''', 'not decided yet'),
    ('type_failure_attr', '''
f = (g:generator<int failure=string>):>void => {}
main = ():>void => {}
''', 'not decided yet'),
    ('yield_place', '''
main = ():>void => {
    let x = 1
    let g = lazy { @x }
    let _ = [g...]
}
''', 'not decided yet'),
    ('loop_mut_gen', '''
main = ():>void => {
    let g = lazy (1 2)
    loop @x in g { x += 1 }
}
''', 'not decided yet'),
    ('return_in_lazy', '''
main = ():>void => {
    let g = lazy { return 1 }
    let _ = [g...]
}
''', 'not allowed inside a lazy generator'),
    ('continue_non_loop_lazy', '''
main = ():>void => {
    let g = $done lazy { 1; continue $done }
    let _ = [g...]
}
''', 'cannot \'continue\''),
    ('non_fresh_spread_param', '''
add = (a:int b:int):>int => a + b
f = (g:generator<int>):>int => add(g...)
main = ():>void => {}
''', 'multivalue'),
    ('non_fresh_spread_pulled', '''
add = (a:int b:int):>int => a + b
main = ():>void => {
    let g = lazy (1 2 3)
    loop x in g { break }
    let _ = add(g...)
}
''', 'multivalue'),
    ('non_fresh_spread_dynamic', '''
add = (a:int b:int):>int => a + b
main = ():>void => {
    let _ = add(lazy loop i in [0..2) { i }...)
}
''', 'multivalue'),
]


@pytest.mark.core_quick
@pytest.mark.parametrize('name,source,expected', REJECT_CASES, ids=[c[0] for c in REJECT_CASES])
def test_generators_core_rejections(compiler, tmp_path, name, source, expected):
    src = tmp_path / f'{name}.dewy'
    out = tmp_path / name
    src.write_text('$runtime_checks\n' + source)
    res = subprocess.run([compiler, 'build', src, '-o', out], capture_output=True, text=True, timeout=30)
    assert res.returncode != 0, f'expected compile failure for {name}'
    combined = (res.stdout + res.stderr).lower()
    assert expected.lower() in combined, f'expected {expected!r} in:\n{res.stdout}{res.stderr}'
