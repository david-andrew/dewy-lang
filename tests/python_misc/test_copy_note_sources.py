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
