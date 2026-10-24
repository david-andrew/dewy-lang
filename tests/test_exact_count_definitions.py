"""Shift counts keep their bounded values through immutable integer conversions."""
import subprocess

import pytest
from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_masked_and_refined_counts(compiler, tmp_path, release):
    source = tmp_path / 'counts.dewy'
    source.write_text('''
masked=(x:int64 by:int64):>int64=>{
    let count:uint64=uint64<overflow='wrap'>(by%32)
    return (x<<count)>>count
}
refined=(x:int64 by:int64<0 <=? by and by <? 63>):>int64=>(x<<by)>>by
changed=(x:int64):>int64=>{
    let count:uint64=uint64<overflow='wrap'>(x%32)
    count=63
    return (x<<count)>>count
}
main=(args:array<string>)=>{
    let x=int64(to_int(args[1]) ?? 0)
    let by=int64(to_int(args[2]) ?? 0)
    printl(masked(x by) refined(x by%63) changed(x))
}
''')
    binary = tmp_path / 'counts'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for x in [-2**63, -1, 0, 1, 2**63-1]:
        for by in [-2**63, -1, 0, 31, 32, 62, 63, 2**63-1]:
            ran = subprocess.run([binary, str(x), str(by)], capture_output=True, text=True)
            assert ran.returncode == 0 and ran.stdout.strip() == f'{x} {x} {x}', ran.stdout + ran.stderr


@pytest.mark.core_quick
def test_constant_power_survives_unrelated_proof_slice(compiler, tmp_path):
    source = tmp_path / 'power.dewy'
    source.write_text('''$runtime_checks
$no_assumed_bounds
pick=(value:int64 unused:uint64):>int64=>value
printl(pick(int64(11)^int64(3) uint64(int64.max)))
''')
    result = subprocess.run([compiler, source], capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == '1331\n', result.stdout + result.stderr
