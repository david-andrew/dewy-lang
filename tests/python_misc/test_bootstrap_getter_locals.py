"""Scope borrows remove record reads without weakening value boundaries."""
import subprocess
from pathlib import Path

from tests.python_misc.test_bootstrap_lowering import ARENA, build_native_lowering_driver
from tests.python_misc.test_bootstrap_scalar_projection import check_native_projection
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_getter_locals(binary, tmp_path):
    source = tmp_path / 'getter-locals.dewy'
    source.write_text(ARENA + (ROOT / 'tests/fixtures/native_getter_locals.dewy').read_text())
    lowered = subprocess.run([binary, source], capture_output=True, text=True, timeout=60)
    assert lowered.returncode == 0, lowered.stdout + lowered.stderr
    assert '__dewy_borrow_' in lowered.stdout
    output = source.with_suffix('.udewy')
    output.write_text(lowered.stdout)
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=15)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)


def test_native_getter_locals(tmp_path):
    binary = build_native_lowering_driver(tmp_path)
    check_getter_locals(binary, tmp_path)
    check_native_projection(binary, tmp_path)
