"""Typed snapshots retain graph identities and reject incomplete data."""
import subprocess
import sys
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_snapshot_values(tmp_path):
    source = ROOT / 'tests/fixtures/native_cache_snapshot.dewy'
    output = tmp_path / 'snapshot.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)


def test_generated_snapshot_codec_is_current():
    result = subprocess.run([sys.executable, ROOT / 'tools/generate_native_cache.py', '--check'],
                            cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
