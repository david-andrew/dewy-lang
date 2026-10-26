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


def test_conversions_keep_the_value_and_keys_are_a_set():
    n, d = gen.Var(gen.I, 'n'), gen.Var(gen.DII, 'd')
    fits, unfit = gen.Conv(gen.U, gen.Lit(gen.I, 3), tag=1), gen.Conv(gen.U, n, tag=2)
    unseen = gen.Conv(gen.I, gen.Lit(gen.U, 2 ** 63), tag=3)
    body = (gen.Let('n', gen.I, gen.Lit(gen.I, -1)),
            gen.Let('d', gen.DII, gen.DictLit(gen.DII, ((gen.Lit(gen.I, -3), gen.Lit(gen.I, 1)),))),
            gen.Print(fits), gen.Print(unfit), gen.If(gen.Lit(gen.B, False), (gen.Print(unseen),)),
            gen.Print(gen.Method(gen.SI, d, 'keys')), gen.Print(gen.Collect(gen.AI, gen.Method(gen.SI, d, 'keys'))))
    program = gen.fill_asserts(gen.Program((), body))
    source = program.source()
    assert 'uint64(int64(3))' in source and "uint64<overflow='wrap'>(n)" in source and "int64<overflow='wrap'>(" in source
    assert program.outcome() == ('3\n18446744073709551615\nset[-3]\n[-3]\n', 0)
    assert gen.Program((), body).outcome()[1] == 101  # unsettled, the unfit conversion is checked


def test_fuzz_smoke(compiler, tmp_path):  # noqa: F811
    started = time.monotonic()  # the limit below only catches hangs; load makes builds slow
    status = dewy_fuzz.fuzz(compiler, seed=1, count=3, modes=('native', 'web'), shrink=0, quiet=True,
                            failures_dir=tmp_path / 'failures', work=tmp_path / 'work')
    assert status == 0, sorted(p.name for p in (tmp_path / 'failures').iterdir())
    assert time.monotonic() - started < 120
