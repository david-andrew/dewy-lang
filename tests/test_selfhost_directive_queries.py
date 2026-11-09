"""Policy queries (the trap policy at a position, uniform files, no-traps bodies, builtin setting
names, assumed bounds by file, explicit copies, proven indexes) agree with frozen Jo: both compilers
build programs that use settings, with the same messages and bytes."""
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_directive_rules import CASES, MIXED, outcome

EXTRA = sorted([*(ROOT / 'tests/cases/parallel_range_bound').glob('*.dewy'),
                *(ROOT / 'tests/cases/dogfood34_proofs').glob('*.dewy'),
                *(ROOT / 'tests/cases/arena').glob('*copies*.dewy'),
                *(ROOT / 'tests/cases/copies').glob('*.dewy')])


def test_directive_queries_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    (tmp_path / 'mixed.dewy').write_text(MIXED)
    dewy, jo = leaf_compilers(compiler, tmp_path, ('directive_queries',))
    paths = [*CASES, *EXTRA]
    expected = outcome(jo, tmp_path, 'jo', paths)
    assert outcome(dewy, tmp_path, 'dewy', paths) == expected
    assert any(r[1] == 0 for r in expected) and any(r[1] != 0 for r in expected)
    assert any('prototype:' in r[3] for r in expected)
