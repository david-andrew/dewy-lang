"""Cleared internal array handles survive dictionary copy-on-write."""
import os
import subprocess

import pytest
from driver_artifacts import isolated_codegen
from test_sloppy_bridge import DEWY_CASES

from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_native_array_dictionary_tombstones(tmp_path):
    if not os.environ.get('DEWY_TEST_DRIVER_COMPILER'):
        pytest.skip('set DEWY_TEST_DRIVER_COMPILER to the current native CLI')
    source = tmp_path / 'tombstones.dewy'
    source.write_text(DEWY_CASES['array-dictionary-tombstones'])
    output = source.with_suffix('.udewy')
    isolated_codegen(output, source, debug_locations=False)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                timeout=10, check=False)
        assert result.returncode == 42, (target, result.returncode, result.stderr)
