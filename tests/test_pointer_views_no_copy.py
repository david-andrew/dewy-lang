"""`.ptr` of an array or string view only read through copies nothing: a string parameter's
bytes (`(s as array<uint8>).ptr + start`, bound with `let` or passed on), and an element of an
`@` parameter's field. Each function calls only its callees, no copy or detach."""
import platform
import re
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

SOURCE = '''
T:type=[names:array<string> hs:array<int64>]
first=(p:ptr<uint8>):>int64=>$unsafe int64(p[0])
look=(@t:T p:ptr<uint8>):>int64=>{
    $unsafe
    first((t.names[0] as array<uint8>).ptr) + first(p)
}
via_param=(@t:T s:string start:int64):>int64=>{
    $unsafe
    look(@t (s as array<uint8>).ptr + start)
}
via_let=(s:string start:int64):>int64=>{
    $unsafe
    let p=(s as array<uint8>).ptr + start
    first(p)
}
main=():>void=>{
    let big=(fill(uint8(97) 100000) as string | none) ?? ""
    let t:T=[[big] []]
    let s:int64=0
    loop i in [0..30) {
        s+=via_param(@t big 1)
        s+=via_let(big 2)
    }
    printl(s)
}
'''

# The exact sum crosses a fixed-width return boundary. Its overflow diagnostic
# does not copy or detach either view.
CALLEES = {'via_let': {'first'}, 'via_param': {'look'}, 'look': {'first', '__panic_bounds', '__int_overflow'}}


@pytest.mark.parametrize('flags', [[], ['--release']], ids=['default', 'release'])
def test_pointer_views_copy_nothing(compiler, tmp_path, flags):
    path = tmp_path / 'views.dewy'
    path.write_text(SOURCE)
    binary = tmp_path / 'views'
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0 and ran.stdout == f'{30 * 3 * 97}\n', ran.stdout + ran.stderr
    if platform.machine().lower() not in ('x86_64', 'amd64') or not shutil.which('objdump'):
        return
    for function, allowed in CALLEES.items():
        code = subprocess.check_output(['objdump', '-d', f'--disassemble={function}', binary], text=True)
        if f'<{function}>:' not in code:
            continue  # (inlined)
        called = set(re.findall(r'\bcall\s+[0-9a-f]+ <([^>]+)>', code))
        assert called <= allowed, (function, called, code)
