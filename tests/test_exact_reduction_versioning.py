"""Array range guards select exact reductions; failures retain scalar order."""
import platform
import re
import subprocess

import pytest

from tests.support import compiler


PROGRAM = '''
kernel=(xs:array<int64> ys:array<int64> rounds:int64):>int64=>{
    $runtime_checks
    let total:int64=0
    loop r in [int64(0)..rounds) {
        loop i in [int64(0)..int64(32)) {total+=(xs[i]+ys[i]) xor r}
    }
    return total
}
main=(args:array<string>)=>{
    let x=int64(to_int(args[1]) ?? 0)
    let y=int64(to_int(args[2]) ?? 0)
    let rounds=int64(to_int(args[3]) ?? 0)
    let xs:array<int64>=[loop i in [0..32) x]
    let ys:array<int64>=[loop i in [0..32) y]
    printl(kernel(xs ys rounds))
}
'''


@pytest.mark.parametrize('release', [False, True])
def test_reduction_guard_and_scalar_fallback(compiler, tmp_path, release):
    source = tmp_path / 'reduce.dewy'
    source.write_text((PROGRAM) + "\n$runtime_checks\n")
    binaries = []
    for debug in [False, True]:
        binary = tmp_path / ('scalar' if debug else 'vector')
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        if not debug and platform.machine().lower() in ('x86_64', 'amd64'):
            body = next((b for b in re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
                         if b.startswith('f_kernel_')), built.stdout)
            assert ' = vld ' in body, body
        binaries.append(binary)
    cases = [(1, 3, 10), (0, 0, 3), (-1, 2, 10), (2**63-1, 0, 1),
             (-2**63, 2**63-1, 1), (2**63-1, 2**63-1, 1),
             (-2**63, -2**63, 0), (4, 7, -1), (2**50, 0, 31)]
    for values in cases:
        outputs = [subprocess.run([b, *map(str, values)], capture_output=True, text=True, timeout=10)
                   for b in binaries]
        assert (outputs[0].returncode == 0) == (outputs[1].returncode == 0), values
        assert outputs[0].stdout == outputs[1].stdout, values


def test_accumulator_snapshot_is_not_an_independent_increment(compiler, tmp_path):
    source = tmp_path / 'recurrence.dewy'
    source.write_text(('''
kernel=(xs:array<int64> count:int64):>int64=>{
    let total:int64=0
    loop i in [int64(0)..count) {
        let snapshot=total
        total+=snapshot+xs[0]
    }
    return total
}
main=(args:array<string>)=>printl(kernel([1] int64(to_int(args[1]) ?? 0)))
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'recurrence'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    safe = subprocess.run([binary, '63'], capture_output=True, text=True)
    assert safe.returncode == 0 and safe.stdout.strip() == str(2**63-1)
    overflow = subprocess.run([binary, '64'], capture_output=True, text=True)
    assert overflow.returncode != 0 and not overflow.stdout
