"""The targeted differential fuzzer: its generators and oracle, and the wrong-code repros it found.

The fuzzing itself is nightly (.github/workflows/fuzz-nightly.yml); these checks are cheap.
"""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401  (fixture)
from tools.compiler import dewy_fuzz_targeted as targeted


def test_every_family_generates_deterministic_tests():
    for family in targeted.FAMILIES:
        for seed in range(40):
            test = targeted.make(family, seed)
            assert test.checks and test.expected, (family, seed)
            assert targeted.make(family, seed).source() == test.source(), (family, seed)


def test_oracle_widths_and_wrapping():
    assert targeted.wrap(128, 'int8') == -128 and targeted.wrap(-1, 'uint16') == 65535
    assert targeted.wrap(2 ** 64, 'uint64') == 0 and targeted.wrap(2 ** 70, 'int') == 2 ** 70
    assert (targeted.low('int32'), targeted.high('uint32')) == (-2 ** 31, 2 ** 32 - 1)
    assert targeted.float_text(1e-7) == '1.0e-07' and targeted.float_text(2.5) == '2.5'


def test_targeted_fuzz_smoke(compiler, tmp_path):  # noqa: F811
    status = targeted.fuzz(compiler, seed=1, count=18, modes=('native', 'native-release'), shrink=0, quiet=True,
                           failures_dir=tmp_path / 'failures', work=tmp_path / 'work')
    assert status == 0, sorted(p.name for p in (tmp_path / 'failures').iterdir())


# Wrong output found by the targeted fuzzer, tracked until fixed. Each runs in the default
# and release builds; a fix makes the strict xfail fail, so the repro moves to tests/cases.
TRACKED = {
    # docs/LANGUAGE.md: fixed-width `^` is computed exactly and storing the result is a checked
    # narrowing; lib/std/dewy.jo's word power wraps instead, silently (int64 and narrower widths,
    # which widen to the int64 word).
    'fixed_width_power_wraps': (('main = ():>void => {\n    let a:int64 = 3037000500\n    printl(a ^ 2)\n'
                                 '    let b:int32 = 2000000000\n    printl(b ^ 3)\n}\n'),
                                '9223372037000250000\n8000000000000000000000000000\n'),
}


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('name', [pytest.param(n, marks=pytest.mark.xfail(
    reason='fixed-width ^ wraps silently instead of the documented exact, checked result', strict=True))
    for n in TRACKED])
def test_tracked_wrong_output(compiler, tmp_path, name, release):  # noqa: F811
    source, expected = TRACKED[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    built = subprocess.run([compiler, 'build', path, '-o', tmp_path / name, *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([tmp_path / name], capture_output=True, text=True, timeout=10, check=False)
    # Either the exact value or a checked overflow failure is acceptable; a wrapped value is not.
    assert ran.stdout == expected or ran.returncode == 101 and 'overflow' in ran.stderr + ran.stdout, ran.stdout
