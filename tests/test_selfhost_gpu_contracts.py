"""GPU boundary contracts retain parity with their frozen compiler twins."""
from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_gpu_sum_panic_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'gpu_float_sum/minimal_float_sum', 'gpu_float_sum/boundaries',
        'gpu_float_sum/buffer_index_bad', 'gpu_float_sum/user_sum_bad',
    ], leaves=('panic_inventory',)) > 0


def test_gpu_nonempty_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [
        'gpu_nonempty/minimal_integer_min', 'gpu_nonempty/guarded',
        'gpu_nonempty/zero_axis_bad', 'gpu_nonempty/unknown_bad',
    ], leaves=('facts_library',)) > 0
