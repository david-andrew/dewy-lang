"""Self-length failures and IR checks, misplaced names, sibling fields, dictionary calls and
proof atoms agree with frozen Jo."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

LEAVES = ('refine_rare',)
PATTERNS = ('self_length/*.dewy', 'sibling_length/*.dewy', 'dict_sibling/*.dewy',
            'record_field_shape/*.dewy', 'default_proofs/*.dewy', 'dogfood18_proofs/*.dewy')


def test_refine_self_check_program_twins(compiler, tmp_path, monkeypatch):
    found = {str(p.relative_to(ROOT / 'tests/cases'))[:-5]
             for pattern in PATTERNS for p in (ROOT / 'tests/cases').glob(pattern)}
    assert compare_facts(compiler, tmp_path, monkeypatch, sorted(found), leaves=LEAVES) > 80
