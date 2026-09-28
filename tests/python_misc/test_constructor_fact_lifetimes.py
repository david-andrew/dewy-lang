"""Constructor-local evidence expires after its value has been consumed."""
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.analyze import bounds
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]


def test_constructor_proof_state_grows_linearly(tmp_path, monkeypatch):
    count = 128
    path = tmp_path / 'many_constructors.dewy'
    path.write_text('Pair:type=[first:int64 second:int64]\nwork=(value:int64):>int64=>{\n'
                    + ''.join(f'let pair{i}=Pair[value value]\n' for i in range(count))
                    + 'return value\n}\nmain=():>int64=>work(42)\n')
    original = bounds._BoundsValidator._analyze
    sizes = []

    def observe(self, node, state, *, validate):
        result = original(self, node, state, validate=validate)
        if self.srcfile.path == path:
            sizes.append(len(result))
        return result

    monkeypatch.setattr(bounds._BoundsValidator, '_analyze', observe)
    execute(tmp_path, 'constructor-facts', codegen(SrcFile.from_path(path), debug_locations=False))
    assert sizes and max(sizes) <= 4 * count + 20


def test_native_constructor_proof_state_grows_linearly(tmp_path):
    source = SrcFile.from_path(ROOT / 'tests/fixtures/native_constructor_fact_scaling.dewy')
    execute(tmp_path, 'native-constructor-facts', codegen(source, debug_locations=False))
