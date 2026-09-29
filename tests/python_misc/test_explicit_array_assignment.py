"""An assignment takes the explicit snapshot's owner without copying it again."""
import pytest

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_scalar_projection import execute

GLOBAL = '''$explicit_copies
make=():>array<int64>=>[20 22]
let source=make()
const snapshot=source.copy()
main=():>int64=>{
    source.clear()
    return if snapshot.length=?2 snapshot[0]+snapshot[1] else 1
}
'''
LOCAL = '''$explicit_copies
make=():>array<int64>=>[20 22]
main=():>int64=>{
    let source=make()
    let snapshot:array<int64>=[]
    snapshot=source.copy()
    source.clear()
    return if snapshot.length=?2 snapshot[0]+snapshot[1] else 1
}
'''
CASES = [GLOBAL, LOCAL,
    LOCAL.replace('main=()', 'replace=(@target:array<int64> source:array<int64>):>void=>{target=source.copy();}\nmain=()')
         .replace('snapshot=source.copy()', 'replace(@snapshot source)'),
    LOCAL.replace('snapshot=source.copy()', 'snapshot=source.copy()\nsnapshot=snapshot.copy()'),
    # Fresh literals still require lasting storage when assigned across scopes.
    LOCAL.replace('snapshot=source.copy()', '{snapshot=[20 22].copy()}'),
]


@pytest.mark.parametrize('source', CASES)
def test_assignment_takes_explicit_snapshot(tmp_path, source):
    emitted = codegen(SrcFile(None, source), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.srcfile.path is None]
    assert not any(not note.explicit and 'assigned to' in note.site for note in notes)
    execute(tmp_path, 'explicit-assignment', emitted)


def test_native_explicit_array_assignment(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
