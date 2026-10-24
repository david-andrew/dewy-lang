"""AVX2 qword multiplication keeps the low 64 bits, including cross terms."""
import platform
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_vector_word_products_and_tails(compiler, tmp_path, release):
    values = [0, 1, -1, 2**63-1, -2**63, 2**32+1, -(2**32+3), 0x123456789abcdef]
    sizes = [0, 1, 2, 3, 4, 5, 7, 8, 9, 31, 33]
    source = tmp_path / 'products.dewy'
    source.write_text(("""W:type=int64<overflow='wrap'>
kernel=(xs:array<W> ys:array<W>):>array<W>=>xs .* ys .- xs
main=()=>{
    let values:array<W>=[""" + ' '.join('(' + str(x) + ')' for x in values) + """]
    loop n in [""" + ' '.join(map(str, sizes)) + """] {
        let xs:array<W>=[]
        let ys:array<W>=[]
        loop i in [0..n) {
            xs.push(values[i%values.length])
            ys.push(values[(i*3+1)%values.length])
        }
        loop value in kernel(xs ys) printl(value)
        loop value in kernel(xs xs) printl(value)
    }
}
""") + "\n$runtime_checks\n")
    binary = tmp_path / 'products'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    if platform.machine().lower() in ('x86_64', 'amd64'):
        assert re.search(r' = vbin .*c=2 imm=3 ', built.stdout), built.stdout
    run = subprocess.run([binary], capture_output=True, text=True)
    expected = []
    for n in sizes:
        xs = [values[i % len(values)] for i in range(n)]
        ys = [values[(i * 3 + 1) % len(values)] for i in range(n)]
        for other in (ys, xs):
            expected.extend(((a*b-a + 2**63) % 2**64) - 2**63 for a, b in zip(xs, other))
    assert run.returncode == 0, run.stderr
    assert list(map(int, run.stdout.split())) == expected
