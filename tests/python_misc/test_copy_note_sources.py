"""Copy notes retain the defining source even when a function is imported."""
from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile


def test_imported_copy_notes_use_the_definition(tmp_path):
    dependency = tmp_path / 'dependency.dewy'
    dependency.write_text("""Fact:type=[weight:int64]
let read=(facts:array<Fact>):>int64=>{
    if facts.length=?0 return 0
    let saved=facts[0]
    facts[0].weight=99
    return saved.weight
}
""")
    entry = tmp_path / 'main.dewy'
    entry.write_text('import p"dependency.dewy" as dep\nlet main=():>int64=>dep.read([[42]])\n')
    codegen(SrcFile.from_path(entry), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if 'bound to `saved`' in note.site]
    assert len(notes) == 1
    assert notes[0].srcfile.path.resolve() == dependency.resolve()
    assert 'saved=facts[0]' in notes[0].srcfile.body[notes[0].loc.start:notes[0].loc.stop]


def test_array_view_kernel_reports_required_copies_and_stays_within_budget():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'fixtures/readonly_array_field_view.dewy'
    codegen(SrcFile.from_path(source))
    notes = [note for note in lower.last_copy_notes if note.srcfile.path == source]
    # Two escaping views need ownership; source/destination writes require
    # two independent snapshots. The read-only local itself must stay a view.
    assert len(notes) == 4
    assert {note.site for note in notes} == {'returned', 'stored in a field', 'bound to `saved`', 'bound to `changed`'}


def test_imported_global_copy_notes_use_the_definition(tmp_path):
    dependency = tmp_path / 'dependency.dewy'
    dependency.write_text('Box:type=[value:int64]\nlet original=Box[42]\nlet snapshot=original\n')
    entry = tmp_path / 'main.dewy'
    entry.write_text('import p"dependency.dewy" as dep\nmain=():>int64=>dep.snapshot.value\n')
    codegen(SrcFile.from_path(entry), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.kind == 'record' and 'snapshot' in note.site]
    assert len(notes) == 1
    assert notes[0].srcfile.path.resolve() == dependency.resolve()
    assert 'snapshot=original' in notes[0].srcfile.body[notes[0].loc.start:notes[0].loc.stop]


def test_startup_provenance_survives_proof_erasure_and_direct_codegen(tmp_path):
    from dewy.backend.udewy import codegen_inner
    from dewy.semantic import check, hir
    dependency = tmp_path / 'dependency.dewy'
    dependency.write_text('''Box:type=[value:int64]
$proof
let known=(x:int64<v=>v>?0>):> <x>?0>=>{$assert x>?0}
let original=Box[42]
let snapshot=original
original.copy();
''')
    entry = tmp_path / 'main.dewy'
    entry.write_text('import p"dependency.dewy" as dep\nmain=():>int64=>{dep.known(42) return dep.snapshot.value}\n')
    source = SrcFile.from_path(entry)
    root = check.typecheck_and_resolve(source, include_prelude=True)
    assert isinstance(root, hir.Program)
    assert hir.child_fields(hir.Program) == ('items',)
    codegen_inner(root, source, debug_locations=False)
    selected = [note for note in lower.last_copy_notes if 'snapshot' in note.site or note.explicit]
    assert len(selected) == 2
    for note in selected:
        assert note.srcfile.path.resolve() == dependency.resolve()
        excerpt = note.srcfile.body[note.loc.start:note.loc.stop]
        assert 'snapshot=original' in excerpt or 'original.copy()' in excerpt
