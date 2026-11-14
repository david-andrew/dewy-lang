"""Transferred owners must leave no stack cleanup record in their caller."""
import pytest
from tests.support import compiler  # noqa: F401
from tools import cases


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['native', 'native-release'])
@pytest.mark.parametrize('names', [
    ['ownership/consume_write_drop', 'ownership/refined_array_exit'],
    ['queues/spawn_forward_branch', 'record/inline_function_type'],
], ids=['consuming-owner-exit', 'forwarded-owner-exit'])
def test_spawn_capture_batch_reaches_exit(compiler, tmp_path, mode, names):
    check_batch(compiler, tmp_path, mode, names)


@pytest.mark.parametrize('mode', ['native', 'native-release'])
def test_match_subject_batch_reaches_exit(compiler, tmp_path, mode):
    check_batch(compiler, tmp_path, mode, [
        'copies/strict_unused_function', 'deadlock/reserve_dropped',
        'facts/uint64_range_int_divisor', 'fixed/array_spread_context',
    ])


def check_batch(compiler, tmp_path, mode, names):
    chosen = [cases.parse(cases.CASES / f'{name}.dewy') for name in names]
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    # A real runtime bug must not be hidden by retrying a timeout in isolation.
    outcomes = runner.value_batch(chosen, mode)
    assert len(outcomes) == len(chosen)
    assert all(outcome.ok for outcome in outcomes), outcomes
