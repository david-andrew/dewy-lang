"""Representation conversions reclaim fresh union results after copying."""
from pathlib import Path
import subprocess

from tests.python_misc.test_bootstrap_lowering import ARENA, build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_owned_cell_casts(binary, tmp_path):
    source = tmp_path / 'owned-cells.dewy'
    source.write_text(ARENA + (ROOT / 'tests/fixtures/active_union_records.dewy').read_text())
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    output = source.with_suffix('.udewy')
    output.write_text(result.stdout)
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=15)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)


def test_native_owned_cell_casts(tmp_path):
    check_owned_cell_casts(build_native_lowering_driver(tmp_path), tmp_path)
