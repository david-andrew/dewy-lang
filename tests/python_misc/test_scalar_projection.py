"""Project a direct getter's scalar result without changing its call boundary."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.backend.udewy.lowering_objects import _ObjectLowering
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def execute(tmp_path, name, code, expected=42):
    path = tmp_path / f'{name}.udewy'
    path.write_text(code)
    results = []
    for target in ['x86_64', 'c']:
        assert entry_point(path, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(path).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == expected, result.stdout + result.stderr
        results.append(result)
    return results


def test_scalar_getter_avoids_record_snapshot_allocations(tmp_path, monkeypatch):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/native_scalar_projection.dewy')
    optimized = codegen(source, debug_locations=False)
    with monkeypatch.context() as patch:
        patch.setattr(_ObjectLowering, '_scalar_getter_projection', lambda *_: None)
        baseline = codegen(source, debug_locations=False)
    for result in execute(tmp_path, 'projected', optimized):
        assert list(map(int, result.stdout.split())) == [0, 0, 0]
    for result in execute(tmp_path, 'copied', baseline):
        allocated, _copied, retained = map(int, result.stdout.split())
        assert allocated > 100_000  # Positive control: returning full records costs storage.
        assert retained == 0


def test_projection_preserves_effects_defaults_captures_and_dispatch(tmp_path):
    source = (ROOT / 'tests/fixtures/scalar_projection_effects.dewy').read_text()
    execute(tmp_path, 'effects', codegen(SrcFile(None, source), debug_locations=False))


def test_projected_getter_keeps_runtime_guard(tmp_path):
    source = '''
Node=type of [value:int64]
node_at=(nodes:array<Node> id:addr):>Node=>{
    $runtime_assert id <? nodes.length
    return nodes[id]
}
main=():>int64=>{
    let nodes:array<Node>=[]
    return node_at(nodes 0).value
}
'''
    for result in execute(tmp_path, 'guard', codegen(SrcFile(None, source), debug_locations=False), 101):
        assert 'assertion' in result.stderr.lower()
