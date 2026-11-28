"""Regression tests for callbacks, comprehensions, and shared captures inside lazy generators."""
import subprocess

import pytest

from tests.support import build_case_batch, compiler  # noqa: F401


RUNTIME_CASES = {
    'callback_captures_mutated_set': '''
Item:type = [name:string score:int64 deps:array<string>]

sched = (items:array<Item>):>generator<string> => lazy {
    let done:set<string> = []
    let cleaned = [0]
    defer {
        let xs = [3 1 2].sorted(key=(v) => v)
        if xs.length >? 0 and xs[0] =? 1 { cleaned.push(1) }
    }
    let pending = items.sorted(key=(it) => it.score)
    loop not pending.is_empty {
        let ready = [loop it in pending if it.deps.all((d) => d in? done) it]
        if ready.is_empty break
        let pick = ready.sorted(key=(it) => it.name)[0]
        pending = [loop it in pending if it.name not=? pick.name it]
        done.push(pick.name)
        pick.name
    }
}

main = ():>void => {
    let items = [
        Item["c" 3 ["a" "b"]]
        Item["b" 2 ["a"]]
        Item["a" 1 []]
    ]
    let out = [loop v in sched(items) v]
    $runtime_assert (out =? ["a" "b" "c"])
    let first:array<string> = []
    loop v in sched(items) {
        first.push(v)
        break
    }
    $runtime_assert (first =? ["a"])
}
''',
    'callback_binding_in_lazy': '''
make = ():>generator<bool> => lazy {
    let done:set<string> = []
    let f = (s:string) => s in? done
    done.push("a")
    f("a")
    ["a"].all((d) => d in? done)
    ["b"].all((d) => d in? done)
}

main = ():>void => {
    let out = [loop x in make() x]
    $runtime_assert (out =? [false true false])
}
''',
    'shared_capture_in_lazy': '''
shared_local = ():>generator<int64> => lazy {
    let n:int64 = 0
    let bump = ($capture @n step:int64):>int64 => { n += step; n }
    bump(10)
    n += 5
    bump(2)
    n
}

shared_for_vars = (xs:array<string>):>generator<string> => lazy {
    loop i in 0.. and x in xs {
        let tag = ($capture @i $capture @x):>string => {
            i += 100
            "{i}:{x}"
        }
        tag()
    }
}

main = ():>void => {
    $runtime_assert ([loop v in shared_local() v] =? [10 17 17])
    $runtime_assert ([loop v in shared_for_vars(["x" "y"]) v] =? ["100:x" "101:y"])
}
''',
    'fused_generator_struct_byref_and_lambda': '''
Job:type = [name:string arrival:int64]

ordered_names = (jobs:array<Job>):>generator<string> => lazy {
    let pending = jobs.sorted(key=(j) => j.arrival)
    loop j in pending { j.name }
}

main = ():>void => {
    let out:array<string> = []
    loop x in ordered_names([Job["c" 3] Job["a" 1] Job["b" 2]]) {
        out.push(x)
    }
    $runtime_assert (out =? ["a" "b" "c"])
}
''',
}


@pytest.mark.core_quick
@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_generator_callback_captures(compiler, tmp_path, target, release):
    body = [f'case_{i}()' for i in range(len(RUNTIME_CASES))]
    cmd, err = build_case_batch(compiler, tmp_path, RUNTIME_CASES, body, release, target)
    assert cmd is not None, err
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.core_quick
def test_generator_callback_captures_debug_info(compiler, tmp_path):
    src = tmp_path / 'debug_case.dewy'
    out = tmp_path / 'debug_case'
    src.write_text('$runtime_checks\n' + RUNTIME_CASES['callback_captures_mutated_set'])
    build = subprocess.run([compiler, 'build', '-g', src, '-o', out], capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stdout + build.stderr
    run = subprocess.run([out], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
