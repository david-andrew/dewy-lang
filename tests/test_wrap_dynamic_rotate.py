"""Rotate recognition needs an actual count bound, including its endpoints."""
import platform
import re
import subprocess
import pytest
from tests.support import compiler


@pytest.mark.parametrize('mode', [(), ('--release',), ('--target', 'web'), ('--release', '--target', 'web')])
def test_bounded_dynamic_rotate(compiler, tmp_path, mode):
    source = tmp_path / 'rotates.dewy'
    source.write_text(('''W:type=uint32<overflow='wrap'>
left=(x:W n:int64):>W=>{let k=n&31;return (x<<k)|(x>>(32-k))}
right=(x:W n:int64):>W=>{let k=n&31;return (x>>k)|(x<<(32-k))}
endpoints=(x:W n:int64):>W=>{let k=n&32;return (x<<k)|(x>>(32-k))}
unbounded=(x:W n:int64):>W=>(x<<n)|(x>>(32-n))
main=()=>{
loop n in [-1 0 1 7 31 32 33 64] {
 let x:W=0x87654321
 printl(left(x n));printl(right(x n));printl(endpoints(x n));printl(unbounded(x n))
}
}
''') + "\n$runtime_checks\n")
    result = subprocess.run([compiler, 'run', source, *mode, '--ir'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    numbers = [int(line) for line in result.stdout.splitlines() if re.fullmatch(r'\d+', line)]
    x, mask = 0x87654321, 2**32 - 1
    expected = []
    for n in [-1, 0, 1, 7, 31, 32, 33, 64]:
        k = n & 31
        raw = ((x << n) | (x >> (32-n))) & mask if 0 <= n <= 32 else 0
        expected += [((x << k) | (x >> (32-k))) & mask,
                     ((x >> k) | (x << (32-k))) & mask, x, raw]
    assert numbers == expected, result.stdout
    if '--target' not in mode and platform.machine().lower() in ('x86_64', 'amd64'):
        built = subprocess.run([compiler, 'build', source, *mode, '--ir', '-o', tmp_path / 'rotate'], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        assert ' = rot32 ' in built.stdout
