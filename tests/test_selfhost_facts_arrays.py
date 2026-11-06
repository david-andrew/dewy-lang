"""Array call and reshape facts agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401

CASES = [
    'effects/slice_assign_fixed_no_traps',
    'copies/slice_explicit',
    'numeric/broadcast_unordered',
    'effects/reshape_count_error',
    'byte_read/unproven',
    'directives/scope_module',
    'effects/dotted_lengths_error',
    'effects/slice_assign_length_error',
]


def test_facts_arrays_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, CASES) > 0
