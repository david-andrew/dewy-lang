"""Index evaluation retains array values only across conflicting effects."""
import subprocess
from pathlib import Path

from tests.python_misc.test_bootstrap_lowering import ARENA, build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_index_snapshots(binary, tmp_path):
    source = tmp_path / 'index-snapshots.dewy'
    source.write_text(ARENA + (ROOT / 'tests/fixtures/native_index_snapshots.dewy').read_text())
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    output = source.with_suffix('.udewy')
    output.write_text(result.stdout)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=30, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)


def test_native_index_snapshots(tmp_path):
    check_index_snapshots(build_native_lowering_driver(tmp_path), tmp_path)
