"""The targeted differential fuzzer: its generators and oracle, and the wrong-code repros it found.

The fuzzing itself is nightly (.github/workflows/fuzz-nightly.yml); these checks are cheap.
"""
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
