"""Completed lifecycle classification queries reuse a pass-local cache."""
from pathlib import Path
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT=Path(__file__).resolve().parents[2]


def test_lifecycle_cache_preserves_recursive_queries_without_warm_allocations(tmp_path):
    source=SrcFile.from_path(ROOT/'tests/fixtures/native_lifecycle_resource_cache.dewy')
    execute(tmp_path,'lifecycle-cache',codegen(source,debug_locations=False))
