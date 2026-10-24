"""A call giving a fixed number of values returns them in place, as a `(T T)`, with no array."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCE = '''split = (a:int64) => {
    loop a >? 1000000 { a -= 7 }
    a - 1
    a + 1
}
written = (a:int64):>(int64 int64) => {
    loop a >? 1000000 { a -= 3 }
    a * 2
    a * 3
}
sum = (a:int64 b:int64) => a + b
main = () => {
    let s = 0
    loop i in 0..100 {
        s += sum(split(i))
        s += sum(written(i))
        let f = @split
        let (x y) = f(i)
        s += x + y
    }
    printl(s)
}
'''


@pytest.mark.core_quick
def test_values_return_without_allocation(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'values.dewy'
    source.write_text((SOURCE) + "\n$runtime_checks\n")
    binary = tmp_path / 'values'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    bodies = re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
    for name in ('split', 'written'):
        body = next(b for b in bodies if b.startswith(f'f_{name}_'))
        # (no call at all: no accumulator array made, grown or pushed onto)
        assert not re.search(r'\bcall\b', body), body
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10, check=False)
    assert ran.returncode == 0 and ran.stdout == '45450\n', ran.stdout + ran.stderr
