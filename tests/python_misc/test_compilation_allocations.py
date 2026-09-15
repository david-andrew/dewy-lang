"""Compiler collection policy must not override or leak an embedder's settings."""
import gc

import pytest

from udewy.compilation import compiler_allocation_scope


@pytest.fixture
def collection_policy():
    original = gc.get_threshold()
    enabled = gc.isenabled()
    gc.enable()
    try:
        yield
    finally:
        gc.set_threshold(*original)
        if not enabled:
            gc.disable()


def test_nested_compilations_restore_policy_after_failure(collection_policy):
    gc.set_threshold(700, 12, 15)
    with pytest.raises(ValueError):
        with compiler_allocation_scope():
            assert gc.isenabled()
            assert gc.get_threshold() == (50_000, 12, 15)
            with compiler_allocation_scope():
                assert gc.get_threshold() == (50_000, 12, 15)
            assert gc.get_threshold() == (50_000, 12, 15)
            raise ValueError('compile failed')
    assert gc.get_threshold() == (700, 12, 15)


@pytest.mark.parametrize('threshold,enabled', [(0, True), (700, False), (100_000, True)])
def test_explicit_caller_policy_is_preserved(collection_policy, threshold, enabled):
    gc.set_threshold(threshold, 12, 15)
    if not enabled:
        gc.disable()
    with compiler_allocation_scope():
        assert gc.get_threshold() == (threshold, 12, 15)
        assert gc.isenabled() == enabled
    assert gc.get_threshold() == (threshold, 12, 15)


def test_cycle_collection_remains_enabled(collection_policy):
    gc.set_threshold(700, 12, 15)
    with compiler_allocation_scope():
        import weakref
        class Cycle:
            pass
        value = Cycle()
        value.self = value
        reference = weakref.ref(value)
        del value
        gc.collect()
        assert reference() is None
