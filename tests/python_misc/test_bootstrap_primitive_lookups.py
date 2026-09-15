"""Primitive factory hits avoid key construction without crossing table states."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_primitive_queries_follow_table_forks_and_truncation(tmp_path):
    source = ROOT / 'tests/fixtures/native_primitive_lookups.dewy'
    output = tmp_path / 'primitives.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                         text=True, timeout=10, check=False)
    assert run.returncode == 42, run.stderr
    assert 0 <= int(run.stdout) < 1_000_000
