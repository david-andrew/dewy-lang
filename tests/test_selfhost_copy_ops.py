"""Copy policy, liveness and owned bindings agree with frozen Jo."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401

CASES = [
    'copies/array_field_loop_rejected',
    'queues/repeatable_capture_move',
    'ownership/partial_empty_reuse_rejected',
    'ownership/scalar_use_after_move',
    'copies/immutable_global_records',
    'copies/closure_rejected',
    'copies/method_field_argument_changed',
    'queues/spawn_forward_reuse',
]


def test_copy_ops_twins(compiler, tmp_path, monkeypatch):
    assert compare_moved(compiler, tmp_path, monkeypatch, CASES) > 0
