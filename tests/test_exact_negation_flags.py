"""An immediate negation may use flags; wider expressions must stay exact."""
import subprocess

import pytest

from tests.support import compiler
from tests.test_fixed_exact import build


@pytest.mark.parametrize('release', [False, True])
def test_negation_storage_boundary(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
negate=(a:int64):>int64=>-a
cancel=(a:int64):>int64=>(-a)-1
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    if args[2] =? "cancel" {printl(cancel(a))}
    else {printl(negate(a))}
}
''', release)
    for value in [0, 1, -1, 2**63-1, -2**63+1]:
        ran = subprocess.run([binary, str(value), 'negate'], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == str(-value), ran.stderr
    ran = subprocess.run([binary, str(-2**63), 'negate'], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout
    ran = subprocess.run([binary, str(-2**63), 'cancel'], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == str(2**63-1), ran.stderr
