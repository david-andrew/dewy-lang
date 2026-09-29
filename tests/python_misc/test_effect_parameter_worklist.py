"""Recursive effect propagation owns one summary per parameter binding."""
from pathlib import Path
import subprocess
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/fixtures/effect_parameter_worklist.dewy'


def test_effect_parameter_worklist(tmp_path):
    execute(tmp_path, 'effect-parameter-worklist', codegen(SrcFile.from_path(SOURCE), debug_locations=False))


def test_native_effect_parameter_worklist(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point
    compiled = subprocess.run([build_program_driver(tmp_path), SOURCE, ROOT / 'library', tmp_path / 'cache'],
                              text=True, capture_output=True, timeout=180)
    assert compiled.returncode == 0, compiled.stderr
    output = tmp_path / 'native-effect-parameters.udewy'
    output.write_text(compiled.stdout)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve(), 'native-budget'], capture_output=True, text=True, timeout=20)
        assert run.returncode == 42, run.stdout + run.stderr
