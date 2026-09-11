"""Source borrowing stays distinct from installed failure-reporting code."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_failure_reporting_preserves_source_borrow_effects(tmp_path):
    source = ROOT / 'tests/fixtures/native_borrowing_failure_effects.dewy'
    seed = tmp_path / 'borrowing.udewy'
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(seed).resolve()], timeout=30, check=False)
    assert result.returncode == 42
