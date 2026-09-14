"""Large finite iterator cardinalities must not wrap into empty ranges."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_bootstrap_lowering import build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_wide_ranges(binary, tmp_path):
    source = ROOT / 'tests/fixtures/native_wide_range_counts.dewy'
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    for label, code in [('native', result.stdout), ('hosted', codegen(SrcFile.from_path(source), debug_locations=False))]:
        output = tmp_path / f'wide-ranges-{label}.udewy'
        output.write_text(code)
        for target in ['x86_64', 'c']:
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                 text=True, timeout=15, check=False)
            assert run.returncode == 42, (label, target, run.returncode, run.stdout, run.stderr)


def test_native_wide_ranges(tmp_path):
    check_wide_ranges(build_native_lowering_driver(tmp_path), tmp_path)
