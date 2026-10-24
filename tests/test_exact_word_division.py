"""Word division keeps exact floor semantics at signed endpoints."""
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_word_division_endpoints(compiler, tmp_path, release):
    source = tmp_path / 'division.dewy'
    source.write_text(('''half=(x:int64):>int64=>x//2
third=(x:int64):>int64=>x//(-3)
remain=(x:int64 d:int64):>int64=>(x+0)%d
main=(args:array<string>)=>{
let x=int64(to_int(args[1]) ?? 0)
printl(half(x))
printl(third(x))
printl(remain(x -1))
printl(remain(x 3))
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'division'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary] +
                           (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    if not release:
        half = next(b for b in re.split(r'^fn ', built.stdout, flags=re.MULTILINE) if b.startswith('f_half_'))
        assert 'checked_' not in half and 'mulhs' not in half
    for value in [-2**63, -7, -1, 0, 1, 7, 2**63-1]:
        ran = subprocess.run([binary, str(value)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.splitlines() == list(map(str, [value//2, value//-3, 0, value%3]))
