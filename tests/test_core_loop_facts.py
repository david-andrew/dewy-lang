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
    arguments = [compiler, *(['--internal-fact-policy=require-static'] if strict else []), command, path]
    if command == 'build':
        arguments += ['-o', tmp_path / 'loops']
    return subprocess.run(arguments, text=True, capture_output=True, timeout=60)


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
main=()=>{ let a:array<int64>=[1 2 3]; printl(sum(@a (@ys:array<int64>)=>{if ys.length >? 0 {ys.pop()}})) }
'''
COMBINED_CALLBACK = '''first=(@xs:array<int64> ys:array<int64> step:<(@zs:array<int64>):>void>):>int64=>{
    if xs.length <? 1 return 0
    let t:int64=0
    loop x in xs and y in ys { t=t+xs[0]*y; step(@xs) }
    return t
}
main=()=>{ let a:array<int64>=[1 2 3]; printl(first(@a [1 1 1] (@zs:array<int64>)=>{zs.clear()})) }
'''
# Resizing the array a loop iterates by value is rejected before any fact is needed.
REJECTED = {
    'push': (PUSH, '/loops.dewy:3:33: error: `push` changes the length of `xs`'),
    'later': (LATER, '/loops.dewy:3:44: error: `pop` changes the length of `xs`'),
}
NEGATIVE = {
    'callback': (CALLBACK, ['/loops.dewy:3:48: error: cannot prove index is in bounds: missing upper bound$/',
                            '/loops.dewy:3:33: note: xs.length may have changed at this call$/'], None),
    'combined_callback': (COMBINED_CALLBACK, ['/loops.dewy:4:36: error: cannot prove index is in bounds: missing upper bound$/'],
                          None),
}


@pytest.mark.core_quick
@pytest.mark.parametrize('name', list(REJECTED))
def test_resizing_by_value_sources_is_rejected(compiler, tmp_path, name):
    source, pattern = REJECTED[name]
    result = run(compiler, tmp_path, source, 'check', True)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert not match_patterns([pattern], output), output


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


# Lockstep counters: a combined loop's range binds, then steps after every
# other binder, so it keeps the difference its entry gives it with each
# hidden index; plain counters that step together do the same.
LOCKSTEP = '''lockstep=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and x in xs and y in ys { t=t+ys[i]*x+xs[i] }
    return t
}
later=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs and y in ys and i in 0.. { t=t+ys[i]+xs[i] }
    return t
}
manual=(ys:array<int64>):>int64=>{
    let t:int64=0
    let i:int64=0
    let j:int64=0
    loop j <? ys.length { t=t+ys[i]; i=i+1; j=j+1 }
    return t
}
main=()=>{
    let empty:array<int64>=[]
    printl(lockstep([1 2 3] [4 5]))
    printl(lockstep(empty [4 5]))
    printl(later([1 2 3] [4 5]))
    printl(manual([4 5 6]))
}
'''


@pytest.mark.parametrize('strict', [False, True], ids=['ordinary', 'strict'])
def test_lockstep_counters_prove_and_run(compiler, tmp_path, strict):
    result = run(compiler, tmp_path, LOCKSTEP, 'build', strict)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == '17\n0\n12\n15\n', ran.stdout + ran.stderr


def lockstep_case(body):
    return ('f=(@xs:array<int64> @ys:array<int64>):>int64=>{\n    let t:int64=0\n    ' + body
            + '\n    return t\n}\nmain=()=>{ let a:array<int64>=[1 2 3]; let b:array<int64>=[4 5]; printl(f(@a @b)) }\n')


# An offset counter, a resize, a rebinding or unequal steps break the relation.
LOCKSTEP_NEGATIVE = {
    'offset': (lockstep_case('loop i in 1.. and x in xs and y in ys { t=t+ys[i] }'), '3:49'),
    'resize': (lockstep_case('loop i in 0.. and x in xs and y in ys { if ys.length >? 0 {ys.pop()}; t=t+ys[i] }'), '3:79'),
    'later_resize': (lockstep_case('loop i in 0.. and x in xs and y in ys { t=t+ys[i]; ys.pop(); }'), '3:49'),
    'rebound': (lockstep_case('loop i in 0.. and x in xs and y in ys { i=i+1; t=t+ys[i] }'), '3:56'),
    'unequal': ('f=(@xs:array<int64> @ys:array<int64>):>int64=>{\n    let t:int64=0\n    let i:int64=0\n'
                '    let j:int64=0\n    loop j <? ys.length { t=t+ys[i]; i=i+2; j=j+1 }\n    return t\n}\n'
                'main=()=>{ let a:array<int64>=[1 2 3]; let b:array<int64>=[4 5]; printl(f(@a @b)) }\n', '5:31'),
}


@pytest.mark.parametrize('name', list(LOCKSTEP_NEGATIVE))
def test_broken_lockstep_does_not_prove(compiler, tmp_path, name):
    source, at = LOCKSTEP_NEGATIVE[name]
    result = run(compiler, tmp_path, source, 'check', True)
    output = result.stdout + result.stderr
    assert result.returncode != 0 and f'/loops.dewy:{at}: error: cannot prove index is in bounds' in output, output
    result = run(compiler, tmp_path, source, 'build', False)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert ran.returncode != 0 and 'index' in ran.stderr, ran.stdout + ran.stderr


# `??` and `match` keep the facts their operands and arms leave: a value path
# knows its tag and payload, and only a path's own writes invalidate.
OPTIONAL = '''
coalesced=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs or y in ys { t=t+(x ?? 0)*(y ?? 1) }
    return t
}
matched=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs or y in ys {
        t=t+match x {n:int64=>n <none>=>0}
        match y {
            n:int64=>{ t=t+n }
            <none>=>{}
        }
    }
    return t
}
tested=(xs:array<int64> ys:array<int64>):>int64=>{
    let t:int64=0
    loop x in xs or y in ys { if y isnt? none { t=t+1 } }
    return t
}
kept=(xs:array<int64> o:int64? i:int64):>int64=>{
    if i <? 0 or i >=? xs.length return 0
    let d=o ?? 5
    let e=match o {n:int64=>n <none>=>1}
    return xs[i]+d+e
}
payload=(xs:array<int64> o:int64?):>int64=>{
    match o {
        n:int64=>{ if n >=? 0 and n <? xs.length return xs[n] }
        <none>=>{}
    }
    return 0
}
main=()=>{
    let absent:int64?=none
    printl(coalesced([1 2 3] [4 5]))
    printl(matched([1 2 3] [4 5]))
    printl(tested([1 2 3] [4 5]))
    printl(kept([1 2 3] 7 2))
    printl(kept([1 2 3] absent 9))
    printl(payload([1 2 3] 1))
}
'''


@pytest.mark.parametrize('strict', [False, True], ids=['ordinary', 'strict'])
def test_optional_paths_keep_facts(compiler, tmp_path, strict):
    result = run(compiler, tmp_path, OPTIONAL, 'build', strict)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == '17\n15\n2\n17\n0\n2\n', ran.stdout + ran.stderr


def guarded_case(statement):
    return ('popped=(@xs:array<int64>):>int64=>{ xs.pop(); return 0 }\n'
            'f=(@xs:array<int64> o:int64? i:int64):>int64=>{\n    if i <? 0 or i >=? xs.length return 0\n    '
            + statement + '\n    return xs[i]+popped(@xs)\n}\n'
            'main=()=>{ let a:array<int64>=[1 2 3]; printl(f(@a 1 2)) }\n')


# A write in any arm or default still retires the guard.
OPTIONAL_NEGATIVE = {
    'arm_resize': (guarded_case('match o {n:int64=>{ xs.pop(); } <none>=>{}}'), True),
    'arm_rebind': (guarded_case('match o {n:int64=>{ i=i+n } <none>=>{}}'), True),
    'arm_call': (guarded_case('let d=match o {n:int64=>n <none>=>popped(@xs)}; printl(d)'), False),
    'default_call': (guarded_case('let d=o ?? popped(@xs); printl(d)'), False),
}


@pytest.mark.parametrize('name', list(OPTIONAL_NEGATIVE))
def test_optional_path_writes_kill_facts(compiler, tmp_path, name):
    source, fails = OPTIONAL_NEGATIVE[name]
    result = run(compiler, tmp_path, source, 'check', True)
    output = result.stdout + result.stderr
    assert result.returncode != 0 and '/loops.dewy:5:12: error: cannot prove index is in bounds' in output, output
    result = run(compiler, tmp_path, source, 'build', False)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert (ran.returncode != 0 and 'index' in ran.stderr) == fails, ran.stdout + ran.stderr


# A map loop's lowering reads the library's key array; that never surfaces
# in the program's diagnostics, and its bounds prove like an array's.
MAPS = '''
either=(m:dict<string int64> xs:array<int64>):>int64=>{
    let t:int64=0
    loop k in m or x in xs { t=t+1 }
    return t
}
both=(m:dict<string int64> xs:array<int64>):>int64=>{
    let t:int64=0
    loop k in m and x in xs { t=t+x }
    return t
}
counted=(m:dict<string int64>):>int64=>{
    let t:int64=0
    loop i in 0.. and k in m { t=t+i }
    return t
}
main=()=>{
    let m:dict<string int64>=["a"->1 "b"->2]
    printl(either(m [4 5 6]))
    printl(both(m [4 5 6]))
    printl(counted(m))
}
'''


@pytest.mark.parametrize('strict', [False, True], ids=['ordinary', 'strict'])
def test_map_loops_stay_quiet_and_prove(compiler, tmp_path, strict):
    result = run(compiler, tmp_path, MAPS, 'build', strict)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'warning' not in output, output
    ran = subprocess.run([tmp_path / 'loops'], text=True, capture_output=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == '3\n9\n1\n', ran.stdout + ran.stderr


def test_program_reading_map_keys_is_warned(compiler, tmp_path):
    source = 'main=()=>{\n    let m:dict<string int64>=["a"->1]\n    let e=m.__keys\n    printl(e.length)\n}\n'
    result = run(compiler, tmp_path, source, 'check', False)
    output = result.stdout + result.stderr
    assert "/loops.dewy:3:11: warning: __keys is Map's own, inside the library" in output, output
