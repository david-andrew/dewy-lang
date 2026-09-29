"""Unchanged effect transfers allocate nothing; bounded composition is exact."""
import subprocess
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/fixtures/effect_route_translation.dewy'


def test_effect_route_translation(tmp_path):
    execute(tmp_path, 'effect-route-translation', codegen(SrcFile.from_path(SOURCE), debug_locations=False))


def test_native_effect_route_translation(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    compiled = subprocess.run([build_program_driver(tmp_path), SOURCE, ROOT / 'library', tmp_path / 'cache'],
                              text=True, capture_output=True, timeout=180)
    assert compiled.returncode == 0, compiled.stderr
    execute(tmp_path, 'native-effect-route-translation', compiled.stdout)
