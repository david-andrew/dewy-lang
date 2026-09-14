"""A union of array lengths widens by reading the active descriptor."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_array_union_widening_preserves_descriptors_and_values(tmp_path, monkeypatch):
    source = ROOT / 'tests/fixtures/array_union_widening.dewy'
    output = tmp_path / 'arrays.udewy'
    output.write_text(codegen(SrcFile.from_path(source)))
    monkeypatch.chdir(tmp_path)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=15)
        assert result.returncode == 42, result.stderr.decode()
