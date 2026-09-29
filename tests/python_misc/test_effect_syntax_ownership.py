"""Effect parsing keeps independent results and immutable source snapshots."""
from pathlib import Path

from dewy.backend.udewy import lower

ROOT = Path(__file__).resolve().parents[2]
SOURCES = [ROOT / 'tests/fixtures/strict_effect_syntax.dewy',
           ROOT / 'tests/fixtures/strict_effect_contract_copy.dewy']


def test_native_effect_syntax_ownership(tmp_path, monkeypatch):
    import test_bootstrap_structural_text as harness
    binary = harness.build_program_driver(tmp_path)
    original = harness.codegen
    def checked_codegen(*args, **kwargs):
        generated = original(*args, **kwargs)
        notes = [note for note in lower.last_copy_notes
                 if note.srcfile.path and note.srcfile.path.name == 'effect_syntax.dewy'
                 and note.runtime_sized and not note.policy_exempt]
        assert notes and all(note.explicit for note in notes)
        return generated
    # The paired harness already compiles and executes each hosted case.
    # Check its inventory there, without another compiler-sized C build.
    monkeypatch.setattr(harness, 'codegen', checked_codegen)
    cases = [source.read_text().replace('p"../../dewy/', f'p"{ROOT}/dewy/') for source in SOURCES]
    harness.check_structural_text(binary, tmp_path, cases=cases, errors=[])
