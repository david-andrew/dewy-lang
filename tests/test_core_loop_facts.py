"""Combined loops carry each sequence's index bounds under the strict policy."""
import os
import subprocess

import pytest

from tools.cases import match_patterns
from tests.support import compiler  # noqa: F401

# Lengths are never compile-time constants here. `and` stops at the shortest
# input; every element read (hidden or written) must prove under strict.
PROVED = '''pairs=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs and y in ys { t=t+x*y }
    return t
}
guarded=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs and t <? 100 and y in ys { t=t+x*y }
    return t
}
counted=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs and y in ys { t=t+i*x*y }
    return t
}
indexed=(xs:array<int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs { t=t+xs[i]*x }
    return t
}
below=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop i in [0..xs.length) and y in ys { t=t+xs[i]*y }
    return t
}
through=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    if xs.length <? 1 return 0
    loop i in [0..xs.length-1] and y in ys { t=t+xs[i]+y }
    return t
}
snapshot=(@xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs and y in ys { xs.push(y); t=t+x }
    return t+xs.length
}
either=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs or y in ys { t=t+1 }
    return t
}
same=(a:string b:string):>int64=>{
    let t:int64=0
    loop x in a and y in b { if x =? y t=t+1 }
    return t
}
mixed=(a:string xs:array<int64>):>int64=>{
    let t:int64=0
    loop c in a and x in xs and i in 0.. { t=t+x*i }
    return t
}
main=()=>{
    let empty:array<int64>=[]
    let grown:array<int64>=[1 2]
    printl(pairs([1 2 3] [4 5]))
    printl(pairs(empty [4 5]))
    printl(guarded([10 20 30] [3 4 5]))
    printl(counted([1 2 3] [4 5 6 7]))
    printl(indexed([1 2 3]))
    printl(indexed(empty))
    printl(below([1 2 3] [10 100]))
    printl(through([1 2 3] [10 100 1000 10000]))
    printl(snapshot(@grown [7 8 9]))
    printl(either([1 2] [3 4 5]))
    printl(same("héllo" "hello"))
    printl(mixed("abc" [5 6]))
}
'''
PROVED_OUTPUT = '14\n0\n110\n46\n14\n0\n210\n1116\n7\n3\n4\n6\n'


def run(compiler, tmp_path, source, command, strict):
    path = tmp_path / 'loops.dewy'
    path.write_text(source)
    arguments = [compiler, command, path]
    if command == 'build':
        arguments += ['-o', tmp_path / 'loops']
    env = {**os.environ, **({'DEWY_INTERNAL_FACT_POLICY': 'require-static'} if strict else {})}
    return subprocess.run(arguments, env=env, text=True, capture_output=True, timeout=60)


@pytest.mark.parametrize('strict', [False, True], ids=['ordinary', 'strict'])
def test_combined_loops_prove_and_run(compiler, tmp_path, strict):
    result = run(compiler, tmp_path, PROVED, 'build', strict)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == PROVED_OUTPUT, ran.stdout + ran.stderr


# A body that may resize the original kills its facts, at the resize and,
# for later iterations, at the loop header.
PUSH = '''sum=(@xs:array<int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs { xs.push(x); t=t+xs[i] }
    return t
}
main=()=>{ let a:array<int64>=[1 2 3]; printl(sum(@a)) }
'''
LATER = '''sum=(@xs:array<int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs { t=t+xs[i]; xs.pop() }
    return t
}
main=()=>{ let a:array<int64>=[1 2 3]; printl(sum(@a)) }
'''
CALLBACK = '''sum=(@xs:array<int64> step:<(@ys:array<int64>):>void>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs { step(@xs); t=t+xs[i] }
    return t
}
main=()=>{ let a:array<int64>=[1 2 3]; printl(sum(@a (@ys:array<int64>)=>{ys.pop()})) }
'''
COMBINED_CALLBACK = '''first=(@xs:array<int64> ys:array<int64> step:<(@zs:array<int64>):>void>):>int64=>{
    if xs.length <? 1 return 0
    let t:int64=0
    loop x in xs and y in ys { t=t+xs[0]*y; step(@xs) }
    return t
}
main=()=>{ let a:array<int64>=[1 2 3]; printl(first(@a [1 1 1] (@zs:array<int64>)=>{zs.clear()})) }
'''
NEGATIVE = {
    'push': (PUSH, ['/loops.dewy:3:49: error: cannot prove index is in bounds: missing upper bound$/',
                    '/loops.dewy:3:33: note: xs.length may have changed at this push$/'], '6\n'),
    'later': (LATER, ['/loops.dewy:3:37: error: cannot prove index is in bounds: missing upper bound$/',
                      '/loops.dewy:3:5: note: xs.length may have changed at this loop$/'], None),
    'callback': (CALLBACK, ['/loops.dewy:3:48: error: cannot prove index is in bounds: missing upper bound$/',
                            '/loops.dewy:3:33: note: xs.length may have changed at this call$/'], None),
    'combined_callback': (COMBINED_CALLBACK, ['/loops.dewy:4:36: error: cannot prove index is in bounds: missing upper bound$/'],
                          None),
}


@pytest.mark.core_quick
@pytest.mark.parametrize('name', list(NEGATIVE))
def test_resizing_bodies_kill_loop_facts(compiler, tmp_path, name):
    source, patterns, _ = NEGATIVE[name]
    result = run(compiler, tmp_path, source, 'check', True)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert not match_patterns(patterns, output), output


@pytest.mark.parametrize('name', list(NEGATIVE))
def test_resizing_bodies_keep_runtime_checks(compiler, tmp_path, name):
    source, _, expected = NEGATIVE[name]
    result = run(compiler, tmp_path, source, 'build', False)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    if expected is None:
        assert ran.returncode != 0 and 'index' in ran.stderr, ran.stdout + ran.stderr
    else:
        assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr
