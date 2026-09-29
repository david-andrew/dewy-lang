"""Move a descriptor's last use while preserving live sibling fields."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_optional_record_field_moves import SOURCE

SIBLING = SOURCE.replace('Box:type=[values:array<int64>]', 'Box:type=[values:array<int64> answer:int64=42]')
SIBLING = SIBLING.replace('values.push(22)', 'values.push(22)\n    if maybe.answer not=?42 return 5')
CASES = [SIBLING,
    SIBLING.replace('Box?', 'Box|bool').replace('return none', 'return false').replace('maybe is? none', 'maybe is? bool'),
    SIBLING.replace('let values=maybe.values', 'let values=maybe.values\n    maybe.answer=42'),
]
CASES.append(SIBLING.replace('Box?', 'Box')
    .replace('    if not present return none\n', '').replace('    if maybe is? none return 42\n', ''))
CASES.append(SIBLING.replace('answer:int64=42]', 'answer:int64=42 extra:array<int64>=[7]]')
    .replace('if maybe.answer not=?42', 'if maybe.extra.length not=?1 or maybe.answer not=?42'))
ERRORS = [SIBLING.replace('let values=maybe.values', 'let values=maybe.values\n    if maybe.values.length>?10 return 6'),
    SIBLING.replace('let values=maybe.values', 'const alias=@maybe.values\n    let values=maybe.values\n    if alias.length>?10 return 6'),
]

ERRORS.append(ERRORS[1].replace('const alias=@maybe.values', 'const alias=maybe.values'))

@pytest.mark.parametrize('source', CASES)
def test_sibling_record_field_moves(tmp_path, source):
    execute(tmp_path, 'sibling-field-move', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_live_field_and_alias_keep_copy_obligation(source):
    with pytest.raises(ReportException, match='unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_native_sibling_record_field_moves(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_sibling_field_allocation_positive_control(tmp_path, monkeypatch):
    from dewy.backend.udewy.lower import _Lowerer
    from dewy.semantic import hir
    compute = _Lowerer._compute_moves
    def without_fields(self, literal):
        fields = {id(node) for node in hir.walk(literal.body) if isinstance(node, hir.MemberAccess)}
        return compute(self, literal) - fields
    monkeypatch.setattr(_Lowerer, '_compute_moves', without_fields)
    execute(tmp_path, 'sibling-field-copy-control',
        codegen(SrcFile(None, SIBLING.replace('$explicit_copies', '')), debug_locations=False), expected=3)
