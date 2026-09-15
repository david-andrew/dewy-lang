"""Packed compiler ids preserve independent snapshots at word boundaries."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_dense_id_snapshots_and_duplicate_insert_budget(tmp_path):
    source = ROOT / 'tests/fixtures/native_dense_ids.dewy'
    output = tmp_path / 'dense-ids.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target, debug_info=False)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)
