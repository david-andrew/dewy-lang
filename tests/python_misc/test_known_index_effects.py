"""Proven constant indices retain effects and left-to-right evaluation."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_known_indices_keep_evaluation(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/known_index_effects.dewy')
    execute(tmp_path, 'known-index-effects', codegen(source, debug_locations=False))


def test_contextual_end_keeps_its_proven_value(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/reserved_name_roles.dewy')
    execute(tmp_path, 'known-end-index', codegen(source, debug_locations=False))
