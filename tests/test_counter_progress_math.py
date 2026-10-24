"""Bounded mathematical increments can use the fixed accumulator's axiom."""
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('disabled', [False, True])
def test_masked_mathematical_increment(compiler, tmp_path, disabled):
    source = tmp_path / 'counter.dewy'
    source.write_text((('$no_assumed_bounds\n' if disabled else '') + '''
f=(start:int64 increment:int):>int64=>{
    let total=start
    loop i in [0..2) {total+=increment and 65535}
    return total
}
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0) to_int(args[2]) ?? 0))
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'counter'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    function = next(b for b in re.split(r'^fn ', built.stdout, flags=re.MULTILINE) if b.startswith('f_f_'))
    assert ('overflow_add' in function) == disabled
    increment = 2**100 + 37
    start = 2**62 + 5
    ran = subprocess.run([binary, str(start), str(increment)], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == str(start + 74), ran.stderr
    if disabled:
        ran = subprocess.run([binary, str(2**63-2), '3'], capture_output=True, text=True)
        assert ran.returncode != 0 and not ran.stdout


@pytest.mark.core_quick
def test_static_mathematical_increment_uses_one_narrowing_obligation(compiler, tmp_path):
    source = tmp_path / 'static_counter.dewy'
    source.write_text("""$runtime_checks=false
f=(start:int64 increment:int):>int64=>{
    let total=start
    loop i in [0..2) {total+=increment and 65535}
    return total
}
printl(f(2 18446744073709551653))
""")
    ran = subprocess.run([compiler, source], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout == '76\n', ran.stderr
