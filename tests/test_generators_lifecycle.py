"""Dewy generators v1 lifecycle, delegation, defer, ownership, and failure-as-value tests.

Covers compiler leaves: checker_generators, lower_generators, copy_ops, driver_compile,
facts_changes, facts_forgets, facts_slice_prep, ownership_checks, ownership_hooks,
ownership_types, checker_iterator_rewrites.
"""
import subprocess

import pytest

from tests.support import build_case_batch, compiler  # noqa: F401


RUNTIME_CASES = {
    'delegation_tree_and_lifo': '''
let events:array<string> = []
TreeNode:type = [name:string children:array<TreeNode>]

walk_tree = (node:TreeNode):>generator<string> => lazy {
    defer { events.push("exit:{node.name}") }
    node.name
    loop ch in node.children {
        walk_tree(ch)...
    }
}

main = ():>void => {
    let root = TreeNode[name="root" children=[
        TreeNode[name="a" children=[TreeNode[name="a1" children=[]]]]
        TreeNode[name="b" children=[]]
    ]]
    $runtime_assert ([walk_tree(root)...] =? ["root" "a" "a1" "b"])
    $runtime_assert (events =? ["exit:a1" "exit:a" "exit:b" "exit:root"])

    events.clear()
    let seen:array<string> = []
    loop name in walk_tree(root) {
        seen.push(name)
        if name =? "a1" { break }
    }
    $runtime_assert (seen =? ["root" "a" "a1"])
    $runtime_assert (events =? ["exit:a1" "exit:a" "exit:root"])
}
''',
    'delegation_sequences_and_widening': '''
ReadFailed:type = type of error & [code:int]

seq_spread = (xs:array<int> fx:array<int length=3>):>generator<int> => lazy {
    1
    xs...
    fx...
    99
}

str_spread = (s:string):>generator<uint8> => lazy {
    uint8(91)
    s...
    uint8(93)
}

inner_ints = ():>generator<int> => lazy (10 20)
inner_i32 = ():>generator<int32> => lazy (int32(3) int32(4))

widen_union = ():>generator<int | ReadFailed> => lazy {
    inner_ints()...
    ReadFailed[code=99]
}

widen_i64 = ():>generator<int64> => lazy {
    inner_i32()...
    int64(5)
}

widen_opt = ():>generator<int?> => lazy {
    inner_ints()...
    none
}

fwd_gen = (g:generator<int>):>generator<int> => lazy {
    0
    g...
    100
}

main = ():>void => {
    let fx:array<int length=3> = [4 5 6]
    $runtime_assert ([seq_spread([10 20] fx)...] =? [1 10 20 4 5 6 99])
    $runtime_assert ([str_spread("hi")...] =? [uint8(91) uint8(104) uint8(105) uint8(93)])

    let vals:array<int> = []
    let code = -1
    loop item in widen_union() {
        match item {
            e:ReadFailed => { code = e.code }
            v:int => { vals.push(v) }
        }
    }
    $runtime_assert (vals =? [10 20])
    $runtime_assert (code =? 99)
    $runtime_assert ([widen_i64()...] =? [int64(3) int64(4) int64(5)])
    let opts = [widen_opt()...]
    $runtime_assert (opts.length =? 3)
    $runtime_assert (opts[0] =? 10)
    $runtime_assert (opts[1] =? 20)
    $runtime_assert (opts[2] is? none)

    let raw = lazy (1 2)
    $runtime_assert ([fwd_gen(raw)...] =? [0 1 2 100])
}
''',
    'defer_and_owner_lifecycle': '''
let events:array<string> = []

with_defer = (tag:string):>generator<int> => lazy {
    let seen = 0
    defer { events.push("{tag}:d1:{seen}") }
    seen = 1
    10
    defer { events.push("{tag}:d2:{seen}") }
    seen = 2
    20
}

loop_defer = ():>generator<int> => lazy {
    loop i in [0..3) {
        defer { events.push("iter:{i}") }
        i * 10
    }
}

labeled_defer = ():>generator<int> => $done lazy {
    defer { events.push("done_defer") }
    1
    break $done
    2
}

double_gen = (g:generator<int>):>generator<int> => lazy loop x in g { x * 2 }

main = ():>void => {
    # Pipeline moving generator at last use
    let src = lazy (1 2 3)
    let mapped = double_gen(src)
    $runtime_assert ([mapped...] =? [2 4 6])

    # Fresh drop: defer never registered, must not run
    events.clear()
    { let _fresh = with_defer("fresh") }
    $runtime_assert (events.length =? 0)

    # Temporary in loop header: dropped immediately on break
    events.clear()
    loop x in with_defer("temp") {
        $runtime_assert (x =? 10)
        break
    }
    $runtime_assert (events =? ["temp:d1:1"])

    # Named owner survives loop break; defers run once at finish
    events.clear()
    {
        let named = with_defer("named")
        loop x in named {
            $runtime_assert (x =? 10)
            break
        }
        $runtime_assert (events.length =? 0)
        let rest = [named...]
        $runtime_assert (rest =? [20])
        $runtime_assert (events =? ["named:d2:2" "named:d1:2"])
    }
    $runtime_assert (events =? ["named:d2:2" "named:d1:2"])

    # Suspended drop with 2 defers: runs in LIFO order
    events.clear()
    {
        let g = with_defer("lifo")
        let count = 0
        loop _ in g {
            count += 1
            if count =? 2 { break }
        }
        $runtime_assert (events.length =? 0)
    }
    $runtime_assert (events =? ["lifo:d2:2" "lifo:d1:2"])

    # Defer inside loop: per-iteration and early stop
    events.clear()
    $runtime_assert ([loop_defer()...] =? [0 10 20])
    $runtime_assert (events =? ["iter:0" "iter:1" "iter:2"])

    events.clear()
    loop x in loop_defer() {
        if x =? 10 { break }
    }
    $runtime_assert (events =? ["iter:0" "iter:1"])

    # Defer with break $done
    events.clear()
    $runtime_assert ([labeled_defer()...] =? [1])
    $runtime_assert (events =? ["done_defer"])
}
''',
    'failures_as_values_and_or_throw': '''
ReadFailed:type = type of error & [code:int]

let events:array<string> = []

read_step = (i:int):>int | ReadFailed => {
    if i =? 2 { return ReadFailed[code=42] }
    i * 10
}

stream_with_err = ():>generator<int | ReadFailed> => lazy {
    defer { events.push("err_defer") }
    loop i in [0..5) {
        let v = read_step(i) or_throw
        v
    }
}

consume_or_throw = ():>array<int> | ReadFailed => {
    let out:array<int> = []
    loop x in stream_with_err() or_throw {
        out.push(x)
    }
    out
}

consume_combined_or_throw = ():>array<int> | ReadFailed => {
    let out:array<int> = []
    loop _ in [0..5) and x in stream_with_err() or_throw {
        out.push(x)
    }
    out
}

read_opt = (i:int):>int? | ReadFailed => {
    if i =? 1 { return none }
    if i =? 2 { return ReadFailed[code=7] }
    i
}

stream_selective = ():>generator<int | ReadFailed> => lazy {
    loop i in [0..4) {
        let v = read_opt(i) or_throw<ReadFailed>
        if v is? int { v }
    }
}

main = ():>void => {
    # Inspect failure directly; next pull is EOF and defer runs once
    events.clear()
    let seen:array<int> = []
    let code = -1
    let eg = stream_with_err()
    loop item in eg {
        match item {
            e:ReadFailed => { code = e.code }
            v:int => { seen.push(v) }
        }
    }
    $runtime_assert (seen =? [0 10])
    $runtime_assert (code =? 42)
    $runtime_assert (events =? ["err_defer"])
    $runtime_assert ([eg...].length =? 0)
    $runtime_assert (events =? ["err_defer"])

    # loop x in g or_throw and combined loop or_throw
    events.clear()
    $runtime_assert (consume_or_throw() is? ReadFailed)
    $runtime_assert (events =? ["err_defer"])

    events.clear()
    $runtime_assert (consume_combined_or_throw() is? ReadFailed)
    $runtime_assert (events =? ["err_defer"])

    # Selective or_throw<ReadFailed>
    let sel:array<int> = []
    let sel_err = -1
    loop item in stream_selective() {
        match item {
            e:ReadFailed => { sel_err = e.code }
            v:int => { sel.push(v) }
        }
    }
    $runtime_assert (sel =? [0])
    $runtime_assert (sel_err =? 7)
}
''',
    'drop_hooks_inside_generators': '''
ReadFailed:type = type of error & [code:int]

let drop_sum:int64 = 0
let drop_count:int64 = 0

Guard:type = [
    id:int64
    $__drop__ = ():>void => {
        drop_sum += id
        drop_count += 1
    }
]

fail_now = ():>int | ReadFailed => ReadFailed[code=1]

gen_with_guard = ():>generator<int> => lazy {
    let g = Guard[id=7]
    1
    2
}

gen_fail_guard = ():>generator<int | ReadFailed> => lazy {
    let g = Guard[id=9]
    let v = fail_now() or_throw
    v
}

gen_cap_guard = (g:Guard):>generator<int> => lazy {
    g.id
    1
}

gen_yield_guard = ():>generator<Guard> => lazy {
    let g1 = Guard[id=11]
    g1
    let g2 = Guard[id=22]
    g2
}

main = ():>void => {
    drop_sum = 0; drop_count = 0
    { let _g0 = gen_with_guard() }
    $runtime_assert (drop_count =? 0)

    drop_sum = 0; drop_count = 0
    loop x in gen_with_guard() {
        $runtime_assert (x =? 1)
        break
    }
    $runtime_assert (drop_count =? 1 and drop_sum =? 7)

    drop_sum = 0; drop_count = 0
    $runtime_assert ([gen_with_guard()...] =? [1 2])
    $runtime_assert (drop_count =? 1 and drop_sum =? 7)

    drop_sum = 0; drop_count = 0
    let _fg = [gen_fail_guard()...]
    $runtime_assert (drop_count =? 1 and drop_sum =? 9)

    drop_sum = 0; drop_count = 0
    { let _cg = gen_cap_guard(Guard[id=5]) }
    $runtime_assert (drop_count =? 1 and drop_sum =? 5)

    drop_sum = 0; drop_count = 0
    let ids:array<int64> = []
    loop gd in gen_yield_guard() {
        ids.push(gd.id)
    }
    $runtime_assert (ids =? [int64(11) int64(22)])
    $runtime_assert (drop_count =? 2 and drop_sum =? 33)
}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generators_lifecycle_runtime(compiler, tmp_path, target, release):
    body = [f'case_{i}()' for i in range(len(RUNTIME_CASES))]
    cmd, err = build_case_batch(compiler, tmp_path, RUNTIME_CASES, body, release, target)
    assert cmd is not None, err
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


REJECT_CASES = [
    ('copy_generator_let', '''
main = ():>void => {
    let g = lazy (1 2)
    let g2 = g
    let _ = [g...]
    let _ = [g2...]
}
''', 'move-only'),
    ('pass_then_use_generator', '''
consume = (g:generator<int>):>array<int> => [g...]
main = ():>void => {
    let g = lazy (1 2)
    let _ = consume(g)
    let _ = [g...]
}
''', 'move-only'),
    ('capture_then_use_generator', '''
main = ():>void => {
    let g = lazy (1 2)
    let g2 = lazy loop x in g { x }
    let _ = [g...]
    let _ = [g2...]
}
''', 'move-only'),
    ('delegate_twice_inside_lazy', '''
fwd2 = (g:generator<int>):>generator<int> => lazy {
    g...
    g...
}
main = ():>void => {
    let _ = [fwd2(lazy (1 2))...]
}
''', 'move-only'),
    ('reentry_nested_loop', '''
main = ():>void => {
    let g = lazy (1 2 3)
    loop x in g {
        loop y in g {
            let _ = x + y
        }
    }
}
''', 'while iterating over it'),
    ('reentry_collect', '''
main = ():>void => {
    let g = lazy (1 2 3)
    loop _ in g {
        let _ = [g...]
    }
}
''', 'while iterating over it'),
    ('reentry_combined_loop', '''
main = ():>void => {
    let g = lazy (1 2 3)
    loop a in g and b in g {
        let _ = a + b
    }
}
''', 'twice in the same loop'),
    ('fallible_defer_or_throw', '''
Err:type = type of error
risky = ():>void | Err => Err[]
f = ():>generator<int | Err> => lazy {
    defer { risky() or_throw }
    1
}
main = ():>void => { let _ = [f()...] }
''', 'not decided yet'),
    ('fallible_defer_expr', '''
Err:type = type of error
risky = ():>void | Err => Err[]
f = ():>generator<int> => lazy {
    defer { risky() }
    1
}
main = ():>void => { let _ = [f()...] }
''', 'not decided yet'),
    ('return_in_defer', '''
f = ():>generator<int> => lazy {
    defer { return }
    1
}
main = ():>void => { let _ = [f()...] }
''', 'not allowed inside \'defer\''),
    ('break_out_of_defer', '''
f = ():>generator<int> => lazy {
    loop i in [0..3) {
        defer { break }
        i
    }
}
main = ():>void => { let _ = [f()...] }
''', 'cannot jump out of \'defer\''),
    ('fallible_drop_hook', '''
CloseErr:type = type of error
Bad:type = [
    x:int64
    $__drop__ = ():>void | CloseErr => CloseErr[]
]
main = ():>void => {}
''', 'must return void'),
    ('cancellable_source_in_lazy', '''
CancelSrc:type = [
    n:int64
    next = ():>int64 | none | Canceled => none
]
main = ():>void => {
    let src = CancelSrc[n=0]
    let g = lazy loop x in src { x }
    let _ = [g...]
}
''', 'not decided yet'),
    ('incompatible_delegation', '''
child = ():>generator<string> => lazy ("a" "b")
bad = ():>generator<int> => lazy {
    child()...
}
main = ():>void => { let _ = [bad()...] }
''', 'cannot delegate'),
]


@pytest.mark.core_quick
@pytest.mark.parametrize('name,source,expected', REJECT_CASES, ids=[c[0] for c in REJECT_CASES])
def test_generators_lifecycle_rejections(compiler, tmp_path, name, source, expected):
    src = tmp_path / f'{name}.dewy'
    out = tmp_path / name
    src.write_text('$runtime_checks\n' + source)
    res = subprocess.run([compiler, 'build', src, '-o', out], capture_output=True, text=True, timeout=30)
    assert res.returncode != 0, f'expected compile failure for {name}'
    combined = (res.stdout + res.stderr).lower()
    assert expected.lower() in combined, f'expected {expected!r} in:\n{res.stdout}{res.stderr}'
