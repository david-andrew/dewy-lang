"""Reset guards must preserve exact overflow values until the guard observes them."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build


SOURCE = '''const HIGH:int64=100
reset=(a:int64 b:int64)=>{
 let x=a+b
 let y=a-b
 let z=a*b
 if x <? 0 or x >=? HIGH {x=7}
 if y <? 0 or y >=? HIGH {y=8}
 if z <? 0 or z >=? HIGH {z=9}
 printl(x y z)
}
observed=(a:int64 b:int64)=>{
 let x=a+b
 printl(x)
 if x <? 0 or x >=? 100 {x=7}
 printl(x)
}
inside=(a:int64 b:int64)=>{
 let x=a+b
 if x <? 0 or x >=? 100 {printl(x); x=7}
 printl(x)
}
partial=(a:int64 b:int64)=>{
 let x=a+b
 if x <? 0 or x >=? 100 {if a >? 0 x=7}
 printl(x)
}
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0) let b=int64(to_int(args[2]) ?? 0)
 let word=a+0
 printl(word >=? 0 and word <? 18446744073709551615)
 reset(a b)
 observed(a b)
 inside(a b)
 partial(a b)
}
'''


@pytest.mark.parametrize('release', [False, True])
def test_reset_guard_preserves_observations(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, SOURCE, release)
    for a, b in [(0, 0), (5, 6), (50, 50), (-2**63, -2**63), (2**63-1, 1),
                 (-2**63, -1), (2**63-1, 2**63-1), (2**32, 2**32)]:
        x = a+b
        inside = 0 <= x < 100
        reset = x if inside else 7
        expected = [str(a >= 0).lower(),
                    f'{reset} {a-b if 0 <= a-b < 100 else 8} {a*b if 0 <= a*b < 100 else 9}',
                    str(x), str(reset), *([] if inside else [str(x)]), str(reset),
                    str(7 if not inside and a > 0 else x)]
        run = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert run.returncode == 0 and run.stdout.splitlines() == expected, run.stdout + run.stderr
