"""The reorder variant must not move a statement past a closure call that may stop the program."""
import random

from tools.compiler import dewy_fuzz_programs as gen

I = gen.I


def test_closure_call_counts_as_observable():
    call = gen.Call(I, 'fn', (gen.Lit(I, 1),), closure=True)
    reads, writes, output = gen.effects(gen.Let('r', I, call), ())
    assert output and 'fn' in writes


def test_seed_1925042_reorder_keeps_the_oracle_outcome():
    program, _ = gen.generate(1925042)
    expected = program.outcome()
    for seed in range(40):
        variant = gen.variant_reorder(program, random.Random(seed))
        if variant is not None:
            assert variant.outcome() == expected
            assert not gen.scope_errors(variant)
