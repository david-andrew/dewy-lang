"""`fmt'E'` writes infinities and NaN in capitals, as Python's `E` does; `e`, `f` and `g` keep them lower case."""
import struct
import subprocess

from tests.support import compiler  # noqa: F401

SPECS = ['e', 'E', '.2e', '.2E', '.0E', 'f', '.3f', 'g', 'G', '.3G']


def test_special_values_match_python(compiler, tmp_path):  # noqa: F811
    values = [float('inf'), float('-inf'), float('nan'), 0.0, -0.0, 1.5, -2.25e-7, 1e300]
    bits = [struct.unpack('<Q', struct.pack('<d', v))[0] for v in values]
    shown = '|'.join("{fmt'%s'(x)}" % spec for spec in SPECS)
    source = tmp_path / 'special.dewy'
    source.write_text('main = ():>void => {\n    let bits:array<uint64> = [' + ' '.join(map(str, bits)) + ']\n'
                      '    loop b in bits {\n        let x = b transmute float64\n'
                      f'        printl"{shown}"\n    }}\n}}\n$runtime_checks\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr
    want = ['|'.join(format(v, spec) for spec in SPECS) for v in values]
    assert ran.stdout.splitlines() == want
