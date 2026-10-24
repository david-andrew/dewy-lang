"""Right-shift width facts discharge the following fixed-width store."""
import subprocess

import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_shift_then_add_is_statically_bounded(compiler, tmp_path, release):
    source = tmp_path / 'shift_bounds.dewy'
    source.write_text('''f=(x:int64):>int64=>{
$no_hidden_costs
return (x>>1)+108
}
main=(args:array<string>)=>{
let x=int64(to_int(args[1]) ?? 0)
printl(f(x))
}
''')
    binary = tmp_path / 'shift_bounds'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for x in [-2**63, -1, 0, 1, 2**63-1]:
        ran = subprocess.run([binary, str(x)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == str((x>>1)+108)


def test_shift_of_wide_intermediate_still_needs_check(compiler, tmp_path):
    source = tmp_path / 'wide.dewy'
    source.write_text('f=(x:int64):>int64=>{\n$no_hidden_costs\nreturn ((x<<64)>>63)+1\n}\nmain=()=>printl(f(1))\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'wide'], capture_output=True, text=True)
    assert built.returncode != 0 and 'cannot prove exact integer result fits int64' in built.stderr, built.stderr
