"""Module settings, `match`, generic functions, lambdas and combined loop conditions build
directly as the reference grammar and projection build them, and report the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = '''$runtime_checks
$no_nan=false
$explicit_copies = false
Oops:type = type of error & [message:string]
id = <T>(x:T):>T => x
pick = <A B>(a:A b:B):>A => a
describe = (v:bool|int64|string):>string => match v {
    b:bool => "bool {b}"
    n:int64 => if n >? 3 "big" else "small"
    _ => "other"
}
mode = (name:string):>int64 => match name { <"fast"> => 1 <"slow"> => { let x = 2
    x } _ => 3 }
maybe = (x:int64):>void|Oops => {
    if x >? 3 return Oops("big")
}
main=()=>{
    let k = 5
    let near = (s:string):>int64? => if s.length >? 1 k else none
    let twice = (x:int64) => x * 2
    let total = 0
    let add = ($capture @total x:int64) => { total += x total }
    let xs = [1 2 3 4]
    let i = 0
    loop i <? 4 and xs[i] <? 3 or i =? 9 { i += 1 }
    loop (i >? 0 and i <? 10) and not (i =? 7) { i -= 1 }
    loop xs.length >? 2 xs.pop();
    let found:int64|none = 4
    let size = match found { n:int64 => n <none> => 0 }
    let other = if size >? 100 1 else match found { n:int64 => n } else 9
    match size {
        <-1> => printl("negative")
        _ => printl("{describe(size)} {mode("slow")} {other} {id(i)} {pick(1 "a")}")
    }
    maybe(1);
    printl("{twice(3)} {add(2)} {xs.count(x => x >? 1)} {near("ab")}")
}
'''


def test_direct_flow_identity(compiler, tmp_path):
    source = tmp_path / 'flow.dewy'
    source.write_text(PROGRAM)
    images, outputs = [], []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source, '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, timeout=10)
        assert ran.returncode == 0
        outputs.append(ran.stdout)
    assert images[0] == images[1]
    assert outputs[0] == outputs[1] == b'big 2 4 0 1\n6 2 1 5\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('$runtime_checks=1', ''), ('$realtime', ''), ('$unknown_setting', ''), ('$runtime_checks\n$runtime_checks', ''),
    ('f=<T T>(x:T)=>x', ''), ('f=<>(x:int64)=>x', ''), ('main2=<T>(x:T)=>x\nf=($capture n)=>n', ''),
    ('', 'match 1 { else => 2 }'), ('', 'match 1 { _ => x = 2 }'), ('', 'let none2 = match 1 { none => 2 }'),
    ('', 'match 1 { <1> => 2 } + 1'), ('', 'let f = (a a) => a'), ('', 'let f = ($capture _) => 1'),
    ('', 'loop 1 in [1] and true {}'),
    ('R:type=[f=()=>1]', ''), ('', 'let r=[f=()=>1]')])
def test_migrated_flow_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nmain=():>void=>{{\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
