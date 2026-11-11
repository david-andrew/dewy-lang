"""`fmt'g'` matches Python's `g` format: zero and negative zero, infinities, NaN, and the rounding
that moves a value into or out of exponent form."""
import random
import struct
import subprocess

from tests.support import compiler  # noqa: F401

SPECS = ['g', '.3g', '.10g', '.0g', '.1g', 'G', '.17g']


def test_general_format_matches_python(compiler, tmp_path):  # noqa: F811
    rng = random.Random(7)
    values = [0.0, -0.0, 1.0, -1.0, 0.5, 100.0, 1000.0, 999999.5, 999999.4, 9999995.0, 1e5, 1e6, 123456.0, 1e-4,
              1e-5, 9.9999e-5, 9.99995e-5, float('inf'), float('-inf'), float('nan'), 5e-324, 1.7976931348623157e308,
              0.1, 1 / 3, 1e15, 1e16, 1e22, 123456789.0]
    values += [struct.unpack('<d', struct.pack('<Q', rng.getrandbits(64)))[0] for _ in range(400)]
    values += [rng.uniform(-1, 1) * 10 ** rng.randint(-8, 12) for _ in range(400)]
    values += [rng.randint(1, 999) * 10.0 ** rng.randint(-6, 10) for _ in range(200)]
    bits = [struct.unpack('<Q', struct.pack('<d', v))[0] for v in values]
    shown = '|'.join("{fmt'%s'(x)}" % spec for spec in SPECS)
    source = tmp_path / 'general.dewy'
    source.write_text('$runtime_checks\n\nmain = ():>void => {\n    let bits:array<uint64> = [' + ' '.join(map(str, bits)) + ']\n'
                      '    loop b in bits {\n        let x = b transmute float64\n'
                      f'        printl"{shown}"\n    }}\n}}\n')
    ran = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr
    want = ['|'.join(format(v, spec) for spec in SPECS) for v in values]
    assert ran.stdout.splitlines() == want
