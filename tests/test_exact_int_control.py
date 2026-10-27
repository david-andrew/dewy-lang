"""A fixed destination still checks the selected exact control arm."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('expression', [
    'if choose a*2 else 7',
    'match choose {<true>=>a*2 <false>=>7}',
    'if choose {let x=a*2; x} else 7',
])
def test_selected_arm_checks_fit(compiler, tmp_path, release, expression):
    binary = build(compiler, tmp_path, f'''
f=(a:int64 choose:bool):>int64=>{expression}
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0) args.length >? 2))
''', release)
    for args, expected in [(['9223372036854775807'], '7\n'), (['21', 'yes'], '42\n'),
                           (['9223372036854775807', 'yes'], None)]:
        ran = subprocess.run([binary, *args], capture_output=True, text=True)
        if expected is None:
            assert ran.returncode != 0 and not ran.stdout, ran.stdout + ran.stderr
        else:
            assert ran.returncode == 0 and ran.stdout == expected, ran.stdout + ran.stderr
