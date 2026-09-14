"""Value independence and bounded graph snapshot costs on both native routes."""
import subprocess
from pathlib import Path
from shutil import which

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('fixture', [
    'native_array_sharing',
    'native_array_sharing_raw',
    'native_sharing_contexts',
    'native_refined_union_storage',
    'native_borrowed_string_arrays',
    'native_shared_element_replacement',
    'native_sibling_field_facts',
    'native_set_pop_defaults',
])
def test_array_sharing(tmp_path, fixture):
    seed = tmp_path / f'{fixture}.udewy'
    seed.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures' / f'{fixture}.dewy')))
    for target in ['x86_64', 'c']:
        if target == 'c' and which('cc') is None:
            continue
        assert entry_point(seed, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(seed).resolve()], capture_output=True, text=True, timeout=10, check=False)
        assert result.returncode == 42, result.stdout + result.stderr
        if fixture == 'native_borrowed_string_arrays':
            assert result.stdout == ('abc' * 64 + '\n') * 2
        if fixture == 'native_array_sharing_raw':
            assert int(result.stdout.strip()) > 0  # Positive control for the copy counter.
        if fixture == 'native_sharing_contexts':
            rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
            assert [row[0] for row in rows] == [1000, 100000]
            assert rows[0][1:] == rows[1][1:]
            assert rows[0][1] == 0  # No storage retained by repeated checkers.
            assert rows[0][3] == 0  # No graph backing-buffer copies.
