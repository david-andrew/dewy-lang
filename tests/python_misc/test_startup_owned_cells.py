"""Fresh tagged values retain ownership during module initialization."""
import pytest
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from test_scalar_projection import execute

CASES = [
    '''$explicit_copies
Bounds:type=const [lower:bigint? upper:bigint?]
const empty=Bounds[1 0]
main=():>int64=>{if empty.lower is?none or empty.upper is?none return 1 return if empty.lower=?1 and empty.upper=?0 42 else 2}
''',
    '''$explicit_copies
const zero:bigint?=0
const present:bigint?=42
const absent:bigint?=none
read=(value:bigint?):>int64=>{if value is?none return 7 return if value=?0 0 else 42}
main=():>int64=>if read(zero)=?0 and read(present)=?42 and read(absent)=?7 42 else 4
''',
    '''$explicit_copies
Box:type=[items:array<int64>]
make=():>Box|int64=>Box[[42]]
const widened:Box|int64|none=make()
main=():>int64=>if widened is?Box and widened.items.length=?1 widened.items[0] else 1
''',
]
ERRORS = ['''$explicit_copies
make=():>array<int64>=>[42]
const original:array<int64>|int64=make()
const snapshot:array<int64>|int64|none=original
main=():>int64=>42
''']

@pytest.mark.parametrize('source', CASES)
def test_startup_owned_cells(tmp_path, source):
    execute(tmp_path, 'startup-cells', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_startup_borrowed_cells_still_require_copy(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_startup_owned_cells(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
