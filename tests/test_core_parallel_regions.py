"""Scoped collectors: direct forks, source order, and conservative escape fallbacks."""
import os
import re
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, source, *, release=True):
    path = tmp_path / 'region.dewy'
    path.write_text(source)
    output = tmp_path / 'region'
    run = subprocess.run([compiler, 'build', path, '-o', output, '--ir',
                          *(['--release'] if release else [])],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    return output, run.stdout


def execute(output, workers=1):
    return subprocess.run([output], env=dict(os.environ, SLOPPY_THREADS=str(workers)),
                          capture_output=True, text=True, timeout=30)


@pytest.mark.core_quick
@pytest.mark.parametrize('surface', ['parallel_range(2 (i:int64)=>fork(n-1-i))',
                                     '[parallel i in [0..2) fork(n-1-i)]'])
def test_scalar_fork(compiler, tmp_path, surface):
    output, ir = build(compiler, tmp_path, '''
fork=(n:int64):>int64=>{
 if n <? 2 return n
 let children=''' + surface + '''
 return children[0]+children[1]
}
main=():>void=>{printl"{fork(20)}"}
''')
    run = execute(output)
    assert run.returncode == 0, run.stderr
    assert run.stdout == '6765\n'
    # The native dispatcher retains a promotable stack job. Its sequential
    # version must still be scalar direct recursion, with no environment ABI.
    bodies = re.findall(r'^fn __h_parallel_serial_\d+ \(params 1, ret 0\):.*?(?=^fn |\Z)', ir, re.M | re.S)
    assert bodies, ir
    assert any(not re.search(r'= (slot|load|store) ', body)
               and len(re.findall(r'^\s+v\d+ = call .*b=1 ', body, re.M)) == 2
               for body in bodies), '\n'.join(bodies)
    for workers in (1, 2):
        run = execute(output, workers)
        assert run.returncode == 0, run.stderr
        assert run.stdout == '6765\n'



@pytest.mark.parametrize('release', [False, True])
def test_region_order_and_fallbacks(compiler, tmp_path, release):
    output, _ = build(compiler, tmp_path, '''
emit=(x:int64):>int64=>x
make=():>array<int64>=>[parallel i in [0..2) i+10]
main=():>void=>exit(entry()) entry=()=>{
 let values=[parallel i in [3..5) emit(i)]
 loop value in values {printl"{value}"}
 printl"{values[1]} {values[0]}"
 let escaped=make()
 assert(escaped =? [10 11])
 let changed=[parallel i in [0..2) i]
 changed[0]=9
 assert(changed =? [9 1])
 let nested=[parallel i in [0..2) [parallel j in [0..2) i+j]]
 assert(nested =? [[0 1] [1 2]])
 return 0
}
''', release=release)
    run = execute(output)
    assert run.returncode == 0, run.stderr
    assert run.stdout == '3\n4\n4 3\n'


def test_region_panic(compiler, tmp_path):
    output, _ = build(compiler, tmp_path, '''
main=():>void=>exit(entry()) entry=()=>{
 let values=[parallel i in [0..2) {if i =? 1 panic("region failure") i}]
 printl"{values[0]+values[1]}"
 return 0
}
''')
    run = execute(output)
    assert run.returncode != 0
    assert 'region failure' in run.stderr


@pytest.mark.parametrize('release', [False, True])
def test_nested_borrow_and_escape(compiler, tmp_path, release):
    output, ir = build(compiler, tmp_path, '''
Callback:type=(i:int64):>int64
invoke=(f:Callback):>int64=>f(3)
forward=(f:Callback):>int64=>invoke((i:int64):>int64=>f(i)+f(i+1))
escape=(f:Callback):>Callback=>(i:int64):>int64=>f(i)+1
main=():>void=>exit(entry()) entry=()=>{
 let value:int64=7
 assert(forward((i:int64):>int64=>value+i) =? 21)
 let saved=escape((i:int64):>int64=>value+i)
 let noise=[loop i in [0..1000) "{i}"]
 assert(saved(5) =? 13)
 assert(noise.length =? 1000)
 return 0
}
''', release=release)
    if not release:
        assert 'fn __h_stackenvdrop_' in ir, 'nested callback parameter was not proved borrowed'
    run = execute(output)
    assert run.returncode == 0, run.stderr


def test_region_random_stream_isolation(compiler, tmp_path):
    output, _ = build(compiler, tmp_path, '''
draw_value=(i:int64):>float64=>random()+float64(i)
main=():>void=>exit(entry()) entry=()=>{
 seed_random(17)
 let expected=random()
 seed_random(17)
 let values=[parallel i in [0..2) draw_value(i)]
 assert(values[0] >=? 0.0 and values[1] >=? 1.0)
 assert(random() =? expected)
 return 0
}
''')
    for workers in (1, 2):
        run = execute(output, workers)
        assert run.returncode == 0, run.stderr


def test_region_hidden_callback_context(compiler, tmp_path):
    output, _ = build(compiler, tmp_path, '''
Item:type=[value:int64]
__eq__=(a:Item b:Item):>bool=>{random(); return a.value =? b.value}
observe=(i:int64):>bool=>[Item[i]] =? [Item[i]]
main=():>void=>exit(entry()) entry=()=>{
 seed_random(17)
 let expected=random()
 seed_random(17)
 let values=[parallel i in [0..2) observe(i)]
 assert(values[0] and values[1])
 assert(random() =? expected)
 return 0
}
''')
    for workers in (1, 2):
        run = execute(output, workers)
        assert run.returncode == 0, run.stderr
