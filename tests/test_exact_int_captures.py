"""Private closure word storage preserves the semantic mathematical integer."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build

SOURCE = '''
make=(a:int64)=>{
 let word=a+0
 return ()=>word
}
nested=(a:int64)=>{
 let word=a+0
 return ()=>{let inner=()=>word; inner()}
}
snapshot=(a:int64)=>{
 let word=a+0
 let read=()=>word
 word+=1
 printl(read() word)
}
private=(a:int64)=>{
 let word=a+0
 let step=($capture word)=>{word+=1; word}
 let copy=@step
 printl(step() step() copy())
}
generic=(a)=>{let word=a+0; return ()=>word}
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0)
 let f=make(a) let g=@f
 printl(f() g() nested(a)() generic(a)())
 snapshot(a)
 private(a)
}
'''


@pytest.mark.parametrize('release', [False, True])
def test_word_capture_preserves_exact_values(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, SOURCE, release)
    for a in [-2**63, -2**62-1, -1, 0, 2**62, 2**63-1]:
        run = subprocess.run([binary, str(a)], capture_output=True, text=True)
        expected = [f'{a} {a} {a} {a}', f'{a} {a+1}', f'{a+1} {a+2} {a+1}']
        assert run.returncode == 0 and run.stdout.splitlines() == expected, run.stdout + run.stderr
