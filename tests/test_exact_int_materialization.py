"""Finite two's-complement locals retain every limb at the int ABI boundary."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('flags', [[], ['--release'], ['-g']])
def test_materialize_finite_words(compiler, tmp_path, flags):
    source = tmp_path / 'words.dewy'
    source.write_text('''$runtime_checks
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0)
 let b=int64(to_int(args[2]) ?? 0)
 let two=a*b
 let three=two*a
 let four=three*b
 printl(two three four)
}
''')
    binary = tmp_path / 'words'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    for a, b in [(0, 0), (-1, -1), (-2**63, 1), (-2**63, -1),
                 (-2**63, -2**63), (2**63-1, 2**63-1),
                 (-2**63, 2**63-1), (2**32+1, -(2**32+1))]:
        ran = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == f'{a*b} {a*b*a} {a*b*a*b}\n'
