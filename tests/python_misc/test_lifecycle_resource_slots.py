"""Resource field/element replacement evaluates once and drops the old owner."""
from pathlib import Path
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from tests.python_misc.test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
PRELUDE = '''let changed:int64=0
Handle=type of [id:int64
$__drop__
release=():>void=>{changed=1}
]
Box:type=[item:Handle]
'''
ERRORS = [
    PRELUDE + '''probe=():>void=>{changed=0 let box=Box[Handle[1]]
box.item=Handle[2]
$assert changed=?0
}''',
    PRELUDE + '''probe=():>void=>{changed=0 let items:array<Handle>=[Handle[1]]
items[0]=Handle[2]
$assert changed=?0
}''',
    PRELUDE + '''next=(@items:array<Handle>):>Handle=>{items.clear return Handle[2]}
probe=():>void=>{let items:array<Handle>=[Handle[1]] items[0]=next(@items)}''',
]

@pytest.mark.parametrize('source,diagnostic', list(zip(ERRORS, ['assert', 'assert', 'receiver changes'])))
def test_resource_slot_drop_and_selection_are_checked(source, diagnostic):
    with pytest.raises(ReportException, match=diagnostic):
        codegen(SrcFile(None, source))


def test_resource_slot_replacement(tmp_path):
    execute(tmp_path, 'slots', codegen(SrcFile.from_path(ROOT / 'tests/fixtures/lifecycle_resource_slots.dewy'), debug_locations=False))


def test_native_resource_slot_replacement(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/lifecycle_resource_slots.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=ERRORS)
