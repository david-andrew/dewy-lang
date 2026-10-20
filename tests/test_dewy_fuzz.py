"""The Dewy program fuzzer: its oracle agrees with known outputs, and a tiny run passes."""
import time

from tests.support import compiler  # noqa: F401  (fixture)
from tools.compiler import dewy_fuzz
from tools.compiler import dewy_fuzz_programs as gen


def test_float_text_matches_the_runtime():
    expected = {1e16: '1e+16', 1.2345e-7: '1.2345e-7', 123456789.125: '123456789.125', 0.1: '0.1',
                100.0: '100.0', 1e15: '1000000000000000.0', 12345678901234567.0: '1.2345678901234568e+16',
                0.00001: '0.00001', 3e-5: '0.00003', 1.5e300: '1.5e+300', -2.75: '-2.75', -0.0: '-0.0'}
    for value, text in expected.items():
        assert gen.format_float(value) == text


def test_variants_keep_the_oracle_outcome():
    for seed in range(1, 21):
        program, _ = gen.generate(seed)
        for name, variant in gen.variants(program, seed).items():
            assert variant.outcome() == program.outcome(), (seed, name)
            assert not gen.scope_errors(variant), (seed, name)


def test_fuzz_smoke(compiler, tmp_path):  # noqa: F811
    started = time.monotonic()
    status = dewy_fuzz.fuzz(compiler, seed=1, count=3, modes=('native', 'web'), shrink=0, quiet=True,
                            failures_dir=tmp_path / 'failures', work=tmp_path / 'work')
    assert status == 0, sorted(p.name for p in (tmp_path / 'failures').iterdir())
    assert time.monotonic() - started < 10
