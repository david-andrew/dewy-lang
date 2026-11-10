"""Exact `int` reaches the BigInt library only where a value may leave the machine word, and
then only the code its operations need: each slow operation has its own runtime entry
(lib/math_runtime.jo), and parsing text does not reach the division that printing uses."""
import os
import re
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

SOURCE_ROW = re.compile(r'^source: (?:root|library) -?\d+ (\S.*)$', re.M)

BOUNDED = '''main = ():>void => {
    let a:int = 20
    let b = a * 3 + 1
    $runtime_assert b =? 61
}
'''

# 2^62 - 1 is the largest immediate word: the sums leave it
ADDS = '''main = ():>void => {
    let xs:array<int> = [4611686018427387903 4611686018427387903 -4611686018427387904]
    xs[0] += xs[1]
    xs[2] -= xs[1]
    $runtime_assert xs[0] =? 9223372036854775806
    $runtime_assert xs[2] =? -9223372036854775807
    xs[0] -= xs[1]
    $runtime_assert xs[0] =? 4611686018427387903
}
'''

PARSES = '''main = ():>void => {
    let a = to_int("123456789012345678901234567890") ?? 0
    $runtime_assert a >? 4611686018427387903
}
'''

DIVIDES = '''main = ():>void => {
    let xs:array<int> = [123456789012345678901234567890 7]
    $runtime_assert xs[1] not=? 0
    $runtime_assert xs[0] // xs[1] =? 17636684144620811271604938270
}
'''

# (functions the program must not reach: a body that names nothing fails to check once reached)
DIVISION = ['_mag_divmod', '_mag_reciprocal']
PRODUCTS_AND_BITS = ['_mag_mul_school', '_bitwise']


def build(compiler, tmp_path, source, library=None):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    env = dict(os.environ, **({'DEWY_CORE_LIB': str(library)} if library else {}))
    return subprocess.run([compiler, 'build', '--time', path, '-o', tmp_path / 'program'],
                          env=env, capture_output=True, text=True, timeout=120)


def loaded(result):
    return {os.path.basename(path) for path in SOURCE_ROW.findall(result.stderr)}


def poisoned(tmp_path, names):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    bigint = library / 'bigint.dewy'
    text = bigint.read_text()
    for name in names:
        text, count = re.subn(rf'^((?:let )?{name} ?= ?\(.*=> ?\{{)$', r'\1\n    __reached_but_poisoned()', text,
                              count=1, flags=re.M)
        assert count == 1, name
    bigint.write_text(text)
    return library


def test_bounded_int_does_not_load_bigint(compiler, tmp_path):
    result = build(compiler, tmp_path, BOUNDED)
    assert result.returncode == 0, result.stderr
    assert {'bigint.dewy', 'math_runtime.jo'}.isdisjoint(loaded(result))


def test_unbounded_int_loads_bigint(compiler, tmp_path):
    result = build(compiler, tmp_path, ADDS)
    assert result.returncode == 0, result.stderr
    assert {'bigint.dewy', 'math_runtime.jo'} <= loaded(result)
    run = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('source,unreached', [(ADDS, DIVISION + PRODUCTS_AND_BITS), (PARSES, DIVISION)],
                         ids=['adds', 'parses'])
def test_slow_paths_reach_only_their_code(compiler, tmp_path, source, unreached):
    result = build(compiler, tmp_path, source, poisoned(tmp_path, unreached))
    assert result.returncode == 0, result.stderr
    run = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr


def test_poisoned_code_fails_once_reached(compiler, tmp_path):
    result = build(compiler, tmp_path, DIVIDES, poisoned(tmp_path, DIVISION))
    assert result.returncode != 0
    assert '__reached_but_poisoned' in result.stderr


OPERATIONS = '''main = ():>void => {
    let words:array<string> = ["123456789012345678901234567890" "-98765432109876543210987654321098765432109876543210" "4611686018427387903" "-7"]
    let xs:array<int> = []
    loop w in words {xs.push(to_int(w) ?? 0)}
    loop a in xs {
        loop b in xs {
            $runtime_assert b not=? 0
            printl"{a + b} {a - b} {a * b} {a // b} {a % b} {a and b} {a or b} {a xor b} {a <? b}"
        }
    }
}
'''


def test_slow_operations_match_python(compiler, tmp_path):
    result = build(compiler, tmp_path, OPERATIONS)
    assert result.returncode == 0, result.stderr
    run = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    xs = [123456789012345678901234567890, -98765432109876543210987654321098765432109876543210, 4611686018427387903, -7]
    expected = ''.join(f'{a + b} {a - b} {a * b} {a // b} {a % b} {a & b} {a | b} {a ^ b} {str(a < b).lower()}\n'
                       for a in xs for b in xs)
    assert run.stdout == expected
