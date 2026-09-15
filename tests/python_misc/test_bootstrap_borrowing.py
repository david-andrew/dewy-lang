"""Source borrowing stays distinct from installed failure-reporting code."""
import subprocess
from pathlib import Path
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('fixture', ['native_borrowing_failure_effects', 'native_callback_effects', 'native_analysis_worklists', 'native_index_borrowing', 'native_ambient_graph'])
def test_source_effects_and_storage_boundaries(tmp_path, fixture):
    source = ROOT / f'tests/fixtures/{fixture}.dewy'
    seed = tmp_path / 'borrowing.udewy'
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(seed).resolve()], timeout=30, check=False)
    assert result.returncode == 42
