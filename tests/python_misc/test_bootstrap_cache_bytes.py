"""Internal prelude-cache primitives preserve values and reject partial data."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_cache_binary_values(tmp_path):
    source = ROOT / 'tests/fixtures/native_cache_bytes.dewy'
    output = tmp_path / 'cache-bytes.udewy'
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=15)
        assert result.returncode == 42, (target, result)
