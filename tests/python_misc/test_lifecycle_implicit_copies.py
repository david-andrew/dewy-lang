"""Inferred independent owners call hooks and expose their effects/copy cost."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'tests/fixtures/lifecycle_implicit_copies.dewy').read_text()
ERRORS = [
    """let copies:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{}
$__copy__
duplicate=():>Handle=>{copies+=1 Handle[id]}
]
probe=(@owner:Handle):>int64 & no_effects=>{let snapshot=owner return snapshot.id}
""",
    '$explicit_copies\n' + SOURCE,
    SOURCE.replace('if consume(original) not=?31 return 3', 'consume(original); $assert copies=?1'),
]


def test_implicit_copy_hooks(tmp_path):
    from dewy.backend.udewy import lower
    generated = codegen(SrcFile(None, SOURCE), debug_locations=False)
    notes = [note for note in lower.last_copy_notes if note.site == 'implicit resource copy']
    assert len(notes) == 3 and all(not note.explicit for note in notes)
    execute(tmp_path, 'implicit-copies', generated)


@pytest.mark.parametrize('source,diagnostic', list(zip(ERRORS, ['effect contract', 'explicit_copies', 'assert'])))
def test_implicit_copies_remain_checked(source, diagnostic):
    with pytest.raises(ReportException, match=diagnostic):
        codegen(SrcFile(None, source))


def test_native_implicit_copy_hooks(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[SOURCE], errors=ERRORS)
