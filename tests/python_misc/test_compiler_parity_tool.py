"""Inventory failures must distinguish compilation from program execution."""
import os
import sys

import pytest

from tools.check_compiler_parity import expected_outcome, invoke


@pytest.mark.parametrize('status, stderr', [
    ('timeout', 'Error: stopped'), (-11, 'Error: interrupted'),
    (1, 'Traceback\nError: internal failure'), (1, 'backend failed'),
])
def test_failed_compiler_is_not_a_language_rejection(tmp_path, status, stderr):
    assert not expected_outcome({'accepts': False}, {'compile': {'status': status, 'stderr': stderr}}, tmp_path)


def test_rejection_is_not_expected_program_exit_one(tmp_path):
    result = {'compile': {'status': 1, 'stderr': 'Error: wrong type'}}
    assert expected_outcome({'accepts': False}, result, tmp_path)
    assert not expected_outcome({'accepts': True, 'exit': 1}, result, tmp_path)
    (tmp_path / 'partially-compiled.udewy').write_text('')
    assert not expected_outcome({'accepts': False}, result, tmp_path)


def test_expected_output_is_checked_independently(tmp_path):
    result = {'compile': {'status': 0}, 'run': {'status': 1, 'stdout': 'wrong'}}
    assert expected_outcome({'accepts': True, 'exit': 1}, result, tmp_path)
    assert not expected_outcome({'accepts': True, 'exit': 1, 'stdout': 'expected'}, result, tmp_path)


def test_inventory_captures_raw_output_and_timeouts(tmp_path):
    result = invoke([sys.executable, '-c', 'import os; os.write(1, bytes([255]))'], tmp_path, os.environ, 5)
    assert result['status'] == 0
    assert result['stdout_hex'] == 'ff'
    timed = invoke([sys.executable, '-c', 'import time; time.sleep(60)'], tmp_path, os.environ, .1)
    assert timed['status'] == 'timeout'
